extern "C" {
	#include <lua/lua.h>
	#include <lua/lualib.h>
	#include <lua/lauxlib.h>
}
#include <libwebsockets.h>

#include <iostream>
#include <memory>
#include <unordered_map>
#include <thread>
#include <mutex>
#include <chrono>

#include <fcntl.h>
#include <errno.h>
#include <termios.h>
#include <unistd.h>

using namespace std;

#define LUA_CODE_LEN (1024 * 1024 * 1) // 1 Mb
#define WS_RX_BUFFER_BYTES (LUA_CODE_LEN + 1)
#define PIX_NUM 300
#define LED_NUM (300 * 3)
#define MIN_DELAY 40
#define MAX_DELAY (std::numeric_limits<lua_Integer>::max() - 1)
#define FOREVER_DELAY (std::numeric_limits<lua_Integer>::max())

struct ClientData {
	ClientData()
		: wsi(nullptr)
		, luaCodeBufferSize(0)
		, outputPos(0)
	{

	}

	lws *wsi;
	const lws_context *lwsContext;
	const lws_protocols *lwsProtocol;
	char luaCodeBuffer[LUA_CODE_LEN + 1];
	size_t luaCodeBufferSize;
	struct {
		unsigned char *string;
		size_t length;
	} output[20];
	size_t outputPos;
	mutex outputMutex;

	void print(const char *str) {
		if (outputPos >= sizeof(output)) {
			return;
		}
		output[outputPos].length = strlen(str);
		outputMutex.lock();
		output[outputPos].string = (unsigned char*)malloc(LWS_SEND_BUFFER_PRE_PADDING +
			output[outputPos].length + 1 + LWS_SEND_BUFFER_POST_PADDING);
		memcpy(output[outputPos].string + LWS_SEND_BUFFER_PRE_PADDING, str,
			output[outputPos].length + 1);
		outputPos++;
		outputMutex.unlock();
		lws_callback_on_writable_all_protocol(lwsContext, lwsProtocol);
		cout << wsi << ' ' << str << endl;
	}
};

unordered_map<lws*, ClientData> g_clientsData;
int gSerialPort = -1;
mutex gLuaMutex;
char gLuaCode[LUA_CODE_LEN + 1] = {0};
volatile lua_Integer gPeriodicReset = 0;
lua_State *L = nullptr;
auto gStartTime = std::chrono::high_resolution_clock::now();

static int lua_timestamp(lua_State *L) {
	lua_pushinteger(L, chrono::duration_cast<chrono::nanoseconds>(
		chrono::high_resolution_clock::now() - gStartTime).count());
	return 1;
}

static int lua_addcolor(lua_State *L) {
	auto color = lua_tointeger(L, 2);
	auto len = lua_rawlen(L, 1);
	lua_pushinteger(L, color >> 16);
	lua_rawseti(L, 1, ++len);
	lua_pushinteger(L, (color & 0xff00) >> 8);
	lua_rawseti(L, 1, ++len);
	lua_pushinteger(L, color & 0xff);
	lua_rawseti(L, 1, ++len);
    return 0;
}

static int lua_setcolor(lua_State *L) {
	auto color = lua_tointeger(L, 3);
	auto index = (lua_tointeger(L, 2) - 1) * 3;
	lua_pushinteger(L, color >> 16);
	lua_rawseti(L, 1, ++index);
	lua_pushinteger(L, (color & 0xff00) >> 8);
	lua_rawseti(L, 1, ++index);
	lua_pushinteger(L, color & 0xff);
	lua_rawseti(L, 1, ++index);
    return 0;
}

// TODO: memory allocation limit
bool runLuaSandboxed(const char *code, int periodCounter, uint8_t result[LED_NUM], lua_Integer *delay, ClientData *client = nullptr) {
	lua_getglobal(L, "run_sandboxed");
	lua_pushstring(L, code);
	lua_pushinteger(L, periodCounter);
	lua_call(L, 2, 3);
	bool success = (bool)lua_toboolean(L, -3);
	if (success) {
		int len = (int)lua_rawlen(L, -2);
		if (len == LED_NUM) {
			for (int i = 1; i <= len; i++) {
				lua_rawgeti(L, -2, i);
				result[i - 1] = (uint8_t) lua_tointeger(L, -1);
				lua_pop(L, 1);
			}
			*delay = (int)lua_tointeger(L, -1);
		} else {
			success = false;
		}
	} else {
		auto error = lua_tostring(L, -2);
		if (client != nullptr) {
			client->print(error);
		} else {
			cout << error << endl;
		}
	}
	lua_pop(L, 3);
	return success;
}

static int wsDataReceived(ClientData &client, const char *chunk, size_t chunkLen, bool terminated) {
	// cout << client.luaCodeBufferSize << ' ' << chunkLen << ' ' << client.luaCodeBufferSize + chunkLen << ' ' << LUA_CODE_LEN << endl;
	if (client.luaCodeBufferSize + chunkLen > LUA_CODE_LEN) {
		return 1;
	}
	size_t luaCodeOrigSize = client.luaCodeBufferSize;
	client.luaCodeBufferSize += chunkLen;
	memcpy(client.luaCodeBuffer + luaCodeOrigSize, chunk, chunkLen);
	if (terminated) {
		client.luaCodeBuffer[client.luaCodeBufferSize] = '\0';
		uint8_t result[LED_NUM];
		lua_Integer delay;
		gLuaMutex.lock();
		if (runLuaSandboxed(client.luaCodeBuffer, 0, result, &delay, &client)) {
			write(gSerialPort, result, LED_NUM);
			if (delay == std::numeric_limits<lua_Integer>::max()) {
				gLuaCode[0] = '\0';
			} else {
				memcpy(gLuaCode, client.luaCodeBuffer, client.luaCodeBufferSize + 1);
			}
			gPeriodicReset = delay;
			client.print("Accepted");
		}
		gLuaMutex.unlock();
		client.luaCodeBufferSize = 0;
	}
	return 0;
}

static int wsCallback(lws *wsi, lws_callback_reasons reason, void *user, void *in, size_t len) {

	switch (reason) {
		case LWS_CALLBACK_FILTER_NETWORK_CONNECTION: {
			//lws_filter_network_conn_args *args = (lws_filter_network_conn_args*)user;
			if (g_clientsData.size() > 8) { // TODO: configurable limit
				return -1; // disconnect
			}
			break;
		}

		case LWS_CALLBACK_ESTABLISHED: {
			g_clientsData[wsi].wsi = wsi;
			g_clientsData[wsi].lwsContext = lws_get_context(wsi);
			g_clientsData[wsi].lwsProtocol = lws_get_protocol(wsi);
			break;
		}

		case LWS_CALLBACK_CLOSED: {
			g_clientsData.erase(wsi);
			break;
		}

		case LWS_CALLBACK_RECEIVE: {
			auto iClientData = g_clientsData.find(wsi);
			if (iClientData == g_clientsData.end() || iClientData->second.wsi == NULL) {
				break;
			}
			if (wsDataReceived(iClientData->second, (char*)in, len, lws_is_final_fragment(wsi)) != 0) {
				iClientData->second.wsi = NULL;
				lws_close_reason(wsi, LWS_CLOSE_STATUS_MESSAGE_TOO_LARGE, NULL, 0);
				return -1;
			}
			break;
		}

		case LWS_CALLBACK_SERVER_WRITEABLE: {
			auto iClientData = g_clientsData.find(wsi);
			if (iClientData == g_clientsData.end()) {
				break;
			}
			auto &clientData = iClientData->second;
			if (clientData.wsi == NULL) {
				return -1;
			}
			if (clientData.outputPos <= 0) {
				break;
			}
			clientData.outputMutex.lock();
			auto output = clientData.output[--clientData.outputPos];
			lws_write(wsi, output.string + LWS_SEND_BUFFER_PRE_PADDING, output.length, LWS_WRITE_TEXT);
			free(output.string);
			auto more = (bool)clientData.outputPos > 0;
			clientData.outputMutex.unlock();
			if (more) {
				lws_callback_on_writable_all_protocol(clientData.lwsContext, clientData.lwsProtocol);
			}
			break;
		}

		default: {
			break;
		}
	}

	return 0;
}

static struct lws_protocols protocols[] = {
	{ "ws-protocol", wsCallback, 0, WS_RX_BUFFER_BYTES },
	{ NULL, NULL, 0, 0 },
};

int openSerialPort(const char *name) {
	int serialPort = open(name, O_RDWR);
	if (serialPort < 0) {
		printf("Error %i from open: %s\n", errno, strerror(errno));
		return serialPort;
	}

	termios tty;
	if (tcgetattr(serialPort, &tty) != 0) {
		printf("Error %i from tcgetattr: %s\n", errno, strerror(errno));
		return serialPort;
	}

	tty.c_cflag &= ~PARENB; // disable parity
	tty.c_cflag &= ~CSTOPB; // 1 stop bit
	tty.c_cflag &= ~CSIZE; //
	tty.c_cflag |= CS8; // 8 bits per byte
	tty.c_cflag &= ~CRTSCTS; // disable RTS/CTS hardware flow control
	tty.c_cflag |= CREAD | CLOCAL; // turn on READ & ignore ctrl lines

	tty.c_lflag &= ~ICANON; // disable canonical mode
	tty.c_lflag &= ~ECHO; // disable echo
	tty.c_lflag &= ~ECHOE; // disable erasure
	tty.c_lflag &= ~ECHONL; // disable new-line echo
	tty.c_lflag &= ~ISIG; // disable interpretation of INTR, QUIT and SUSP
	tty.c_iflag &= ~(IXON | IXOFF | IXANY); // turn off s/w flow ctrl
	tty.c_iflag &= ~(IGNBRK|BRKINT|PARMRK|ISTRIP|INLCR|IGNCR|ICRNL); // disable any special handling of received bytes

	tty.c_oflag &= ~OPOST; // prevent special interpretation of output bytes (e.g. newline chars)
	tty.c_oflag &= ~ONLCR; // prevent conversion of newline to carriage return/line feed

	// non-blocking mode
	tty.c_cc[VTIME] = 0;
	tty.c_cc[VMIN] = 0;

	// set in/out baud rate to be 115200
	cfsetispeed(&tty, B115200);
	cfsetospeed(&tty, B115200);

	if (tcsetattr(serialPort, TCSANOW, &tty) != 0) {
		printf("Error %i from tcsetattr: %s\n", errno, strerror(errno));
		return serialPort;
	}

	return serialPort;
}

thread luaPeriodicThread([&](){
	uint8_t result[LED_NUM];
	lua_Integer delay = 1000;
	lua_Integer counter = 1;
	while (true) {
		if (gPeriodicReset) {
			delay = gPeriodicReset;
			counter = 1;
			gPeriodicReset = 0;
		} else {
			gLuaMutex.lock();
			if (gLuaCode[0] != '\0' && runLuaSandboxed(gLuaCode, counter, result, &delay)) {
				write(gSerialPort, result, LED_NUM);
				if (counter == std::numeric_limits<lua_Integer>::max()) {
					counter = 0;
				} else {
					counter++;
				}
			} else {
				gLuaCode[0] = '\0';
			}
			gLuaMutex.unlock();
		}
		this_thread::sleep_for(chrono::milliseconds(delay % MIN_DELAY));
		for (int i = 0; i < delay / MIN_DELAY; i++) {
			if (gPeriodicReset) {
				break;
			}
			this_thread::sleep_for(chrono::milliseconds(MIN_DELAY));
		}
	}
});

int main() {
	gSerialPort = openSerialPort("/dev/ttyACM1");

	L = luaL_newstate();
	luaL_openlibs(L);

	lua_pushcfunction(L, lua_timestamp);
	lua_setglobal(L, "timestamp");
	lua_pushcfunction(L, lua_addcolor);
	lua_setglobal(L, "addcolor");
	lua_pushcfunction(L, lua_setcolor);
	lua_setglobal(L, "setcolor");

	lua_pushinteger(L, PIX_NUM);
	lua_setglobal(L, "PIX_NUM");
	lua_pushinteger(L, MIN_DELAY);
	lua_setglobal(L, "MIN_DELAY");
	lua_pushinteger(L, MAX_DELAY);
	lua_setglobal(L, "MAX_DELAY");
	lua_pushinteger(L, FOREVER_DELAY);
	lua_setglobal(L, "FOREVER_DELAY");

	if (luaL_dofile(L, "../init.lua") != LUA_OK) {
		fprintf(stderr, "%s", lua_tostring(L, -1));
		return 1;
	}

	// if (luaL_dofile(L, "../test.lua") != LUA_OK) {
	// 	fprintf(stderr, "%s", lua_tostring(L, -1));
	// 	return 1;
	// }

	lws_context_creation_info info;
	memset(&info, 0, sizeof(info));
	info.port = 8000;
	info.protocols = protocols;
	info.gid = -1;
	info.uid = -1;

	struct lws_context *context = lws_create_context(&info);

	while (1) {
		lws_service(context, 1000000);
	}

	lws_context_destroy(context);

	return 0;
}

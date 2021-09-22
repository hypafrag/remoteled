extern "C" {
	#include <lua/lua.h>
	#include <lua/lualib.h>
	#include <lua/lauxlib.h>
}
#include <libwebsockets.h>

#include <iostream>
#include <array>
#include <vector>
#include <string>
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

#define LUA_CODE_LEN (1024 * 1024 * 4)
#define WS_RX_BUFFER_BYTES (LUA_CODE_LEN + 1)
#define PIX_NUM 300
#define LED_NUM (300 * 3)

struct ClientData {
	ClientData()
		: luaCodeBufferSize(0)
	{

	}

	char luaCodeBuffer[LUA_CODE_LEN + 1];
	size_t luaCodeBufferSize;
};

unordered_map<lws*, ClientData> g_clientsData;
int gSerialPort = -1;
mutex gLuaMutex;
char gLuaCode[LUA_CODE_LEN + 1] = {0};
volatile int gPeriodicReset = 0;
lua_State *L = nullptr;
auto gStartTime = std::chrono::high_resolution_clock::now();

static int lua_timestamp(lua_State *L) {	
	lua_pushinteger(L, chrono::duration_cast<chrono::nanoseconds>(
		chrono::high_resolution_clock::now() - gStartTime).count());
    return 1;
}

// TODO: memory allocation limit
bool runLuaSandboxed(const char *code, int periodCounter, uint8_t result[LED_NUM], int *delay) {
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
		// auto message = "Done";
		// lws_write(wsi, (unsigned char*)message, strlen(message), LWS_WRITE_TEXT);
	} else {
		auto error = lua_tostring(L, -2);
		fprintf(stderr, "result is: %s\n", error);
		// lws_write(wsi, (unsigned char*)error, strlen(error), LWS_WRITE_TEXT);
	}
	lua_pop(L, 3);
	return success;
}

static int wsDataReceived(lws *wsi, ClientData &clientData, const char *chunk, size_t chunkLen, bool terminated) {
	if (clientData.luaCodeBufferSize + chunkLen > LUA_CODE_LEN) {
		return 1;
	}
	size_t luaCodeOrigSize = clientData.luaCodeBufferSize;
	clientData.luaCodeBufferSize += chunkLen;
	memcpy(clientData.luaCodeBuffer + luaCodeOrigSize, chunk, chunkLen);
	if (terminated) {
		clientData.luaCodeBuffer[clientData.luaCodeBufferSize] = '\0';
		uint8_t result[LED_NUM];
		int delay;
		gLuaMutex.lock();
		if (runLuaSandboxed(clientData.luaCodeBuffer, 0, result, &delay)) {
			write(gSerialPort, result, LED_NUM);
			memcpy(gLuaCode, clientData.luaCodeBuffer, clientData.luaCodeBufferSize + 1);
			gPeriodicReset = delay;
		}
		gLuaMutex.unlock();
		clientData.luaCodeBufferSize = 0;
	}

	return 0;
}

static int wsCallback(lws *wsi, lws_callback_reasons reason, void *user, void *in, size_t len) {
	int returnedValue = 0;

	switch (reason) {
		case LWS_CALLBACK_FILTER_NETWORK_CONNECTION: {
			//lws_filter_network_conn_args *args = (lws_filter_network_conn_args*)user;
			if (g_clientsData.size() > 8) { // TODO: configurable limit
				returnedValue = 1; // disconnect
			}
			break;
		}

		case LWS_CALLBACK_ESTABLISHED: {
			g_clientsData[wsi];
			break;
		}

		case LWS_CALLBACK_CLOSED: {
			g_clientsData.erase(wsi);
			break;
		}

		case LWS_CALLBACK_RECEIVE: {
			auto iClientData = g_clientsData.find(wsi);
			if (iClientData == g_clientsData.end()) {
				break;
			}
			char *data = (char*)in;
			size_t offset = 0;
			for (size_t i = 0; i < len; i++) {
				if (data[i] == '\0' || data[i] == '`') { // TODO: remove `
					wsDataReceived(wsi, iClientData->second, data + offset, i - offset, true);
					offset = i + 1;
				}
			}
			if (offset != len) {
				wsDataReceived(wsi, iClientData->second, data + offset, len - offset, false);
			}
			break;
		}

		default: {
			break;
		}
	}

	fflush(stdout);
	fflush(stderr);

	return returnedValue;
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
	int delay = 1000;
	int counter = 1;
	while (true) {
		if (gPeriodicReset) {
			delay = gPeriodicReset;
			counter = 1;
			gPeriodicReset = 0;
		} else {
			gLuaMutex.lock();
			if (gLuaCode[0] != '\0' && runLuaSandboxed(gLuaCode, counter, result, &delay)) {
				write(gSerialPort, result, LED_NUM);
				if (++counter >= 0x10000) {
					counter = 0;
				}
			}
			gLuaMutex.unlock();
		}
		this_thread::sleep_for(chrono::milliseconds(delay % 50));
		for (int i = 0; i < delay / 50; i++) {
			if (gPeriodicReset) {
				break;
			}
			this_thread::sleep_for(chrono::milliseconds(50));
		}
	}
});

int main() {
	gSerialPort = openSerialPort("/dev/ttyACM2");

	L = luaL_newstate();
	luaL_openlibs(L);

	lua_pushcfunction(L, lua_timestamp);
	lua_setglobal(L, "timestamp");

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

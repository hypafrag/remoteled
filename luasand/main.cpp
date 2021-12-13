extern "C" {
	#include <lua5.3/lua.h>
	#include <lua5.3/lualib.h>
	#include <lua5.3/lauxlib.h>
}
#include <libwebsockets.h>

#include <iostream>
#include <memory>
#include <unordered_map>
#include <thread>
#include <mutex>
#include <chrono>
#include <vector>
#include <string>
#include <algorithm>

#include <fcntl.h>
#include <cerrno>
#include <termios.h>
#include <unistd.h>

#include <dirent.h>

using namespace std;

#define LUA_CODE_LEN (1024 * 1024 * 1) // 1 Mb
#define WS_RX_BUFFER_BYTES (LUA_CODE_LEN + 1)
#define PIX_NUM 300
#define LED_NUM (300 * 3)
#define DELAY_MIN 20
#define DELAY_MAX 999999999
#define DELAY_FOREVER 1000000000

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
		output[outputPos].string = (unsigned char*)malloc(LWS_PRE +
			output[outputPos].length + 1);
		memcpy(output[outputPos].string + LWS_PRE, str,
			output[outputPos].length + 1);
		outputPos++;
		outputMutex.unlock();
		lws_callback_on_writable_all_protocol(lwsContext, lwsProtocol);
		cout << wsi << ' ' << str << endl;
	}
};

unordered_map<lws*, ClientData> gClientsData;
int gSerialPort = -1;
mutex gLuaMutex;
char gLuaCode[LUA_CODE_LEN + 1] = {0};
volatile lua_Integer gPeriodicReset = 0;
lua_State *gLuaState = nullptr;
auto gStartTime = chrono::high_resolution_clock::now();
volatile bool gRunning = true;

static int lua_timestamp(lua_State *L) {
	lua_pushinteger(L, chrono::duration_cast<chrono::nanoseconds>(
		chrono::high_resolution_clock::now() - gStartTime).count());
	return 1;
}

static int lua_addcolor(lua_State *L) {
	auto color = lua_tointeger(L, 2);
	auto len = (lua_Integer)lua_rawlen(L, 1);
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
bool runLuaSandboxed(const char *code, lua_Integer periodCounter, uint8_t result[LED_NUM], lua_Integer *delay, ClientData *client = nullptr) {
	lua_getglobal(gLuaState, "run_sandboxed");
	lua_pushstring(gLuaState, code);
	lua_pushinteger(gLuaState, periodCounter);
	lua_call(gLuaState, 2, 3);
	bool success = (bool)lua_toboolean(gLuaState, -3);
	if (success) {
		int len = (int)lua_rawlen(gLuaState, -2);
		if (len == LED_NUM) {
			for (int i = 1; i <= len; i++) {
				lua_rawgeti(gLuaState, -2, i);
				result[i - 1] = (uint8_t) lua_tointeger(gLuaState, -1);
				lua_pop(gLuaState, 1);
			}
			*delay = (int)lua_tointeger(gLuaState, -1);
		} else {
			success = false;
		}
	} else {
		auto error = lua_tostring(gLuaState, -2);
		if (client != nullptr) {
			client->print(error);
		} else {
			cout << error << endl;
		}
	}
	lua_pop(gLuaState, 3);
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
			if (delay == numeric_limits<lua_Integer>::max()) {
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
			if (gClientsData.size() > 8) { // TODO: configurable limit
				return -1; // disconnect
			}
			break;
		}

		case LWS_CALLBACK_ESTABLISHED: {
			gClientsData[wsi].wsi = wsi;
			gClientsData[wsi].lwsContext = lws_get_context(wsi);
			gClientsData[wsi].lwsProtocol = lws_get_protocol(wsi);
			break;
		}

		case LWS_CALLBACK_CLOSED: {
			gClientsData.erase(wsi);
			break;
		}

		case LWS_CALLBACK_RECEIVE: {
			auto iClientData = gClientsData.find(wsi);
			if (iClientData == gClientsData.end() || iClientData->second.wsi == NULL) {
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
			auto iClientData = gClientsData.find(wsi);
			if (iClientData == gClientsData.end()) {
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

int testCallback(struct lws *wsi, enum lws_callback_reasons reason, void *user, void *in, size_t len) {

	switch (reason) {

		case LWS_CALLBACK_HTTP: {
			auto str = (char*)in;
			uint8_t buf[LWS_PRE + 128], *start = &buf[LWS_PRE], *p = start,
					*end = &buf[sizeof(buf) - 1];
			if (lws_add_http_common_headers(wsi, HTTP_STATUS_OK, "text/plain",
				LWS_ILLEGAL_HTTP_CONTENT_LEN, &p, end)) {
				return 1;
			}
			if (lws_finalize_write_http_header(wsi, start, &p, end)) {
				return 1;
			}
			lws_callback_on_writable(wsi);
			break;
		}

		case LWS_CALLBACK_HTTP_WRITEABLE: {
			size_t bodyLen = 0;
			vector<string> examples;
			auto dir = opendir("examples");
			if (dir == NULL) {
				return 1;
			}
			while (true) {
				auto ep = readdir(dir);
				if (ep == NULL) {
					break;
				}
				auto nameLen = strlen(ep->d_name);
				if (strcmp(ep->d_name + nameLen - 4, ".lua") != 0) {
					continue;
				}
				bodyLen += nameLen + 1;
				examples.emplace_back(ep->d_name);
			}
			sort(examples.begin(), examples.end());
			closedir(dir);

			unsigned char buffer[LWS_PRE + bodyLen], *body = buffer + LWS_PRE, *p = body;
			for (auto &line: examples) {
				memcpy(p, line.c_str(), line.length());
				p += line.length();
				*(p++) = '\n';
			}
			lws_write(wsi, body, bodyLen, LWS_WRITE_HTTP_FINAL);
			if (lws_http_transaction_completed(wsi)) {
				return -1;
			}
			break;
		}

		default: {
			return lws_callback_http_dummy(wsi, reason, user, in, len);
		}
	}

	return 0;
}

// TODO: set .per_session_data_size, use lws_context_user
static struct lws_protocols protocols[] = {
	{ "http", lws_callback_http_dummy, 0, 0 },
	{ "test", testCallback, 0, 0 },
	{ "code", wsCallback, 0, WS_RX_BUFFER_BYTES },
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

thread luaPeriodicThread([](){
	uint8_t result[LED_NUM];
	lua_Integer delay = 1000;
	lua_Integer counter = 1;
	while (gRunning) {
		if (gPeriodicReset) {
			delay = gPeriodicReset;
			counter = 1;
			gPeriodicReset = 0;
		} else {
			gLuaMutex.lock();
			if (gLuaCode[0] != '\0' && runLuaSandboxed(gLuaCode, counter, result, &delay)) {
				write(gSerialPort, result, LED_NUM);
				if (counter == 0xffffff) {
					counter = 0;
				} else {
					counter++;
				}
			} else {
				gLuaCode[0] = '\0';
			}
			gLuaMutex.unlock();
		}
		this_thread::sleep_for(chrono::milliseconds(delay % DELAY_MIN));
		for (int i = 0; i < delay / DELAY_MIN; i++) {
			if (gPeriodicReset) {
				break;
			}
			this_thread::sleep_for(chrono::milliseconds(DELAY_MIN));
		}
	}
});

void exitProcess(int code) {
	gRunning = false;
	luaPeriodicThread.join();
	exit(code);
}

static const struct lws_protocol_vhost_options extraMimes = {
		NULL,				/* "next" linked-list */
		NULL,				/* "child" linked-list */
		".lua",				/* file suffix to match */
		"text/plain"		/* mimetype to use */
};

static struct lws_http_mount examplesListMount = {
		/* .mount_next */		NULL,		/* linked-list "next" */
		/* .mountpoint */		NULL,		/* mountpoint URL */
		/* .origin */			"test",		/* serve from dir */
		/* .def */			NULL,	/* default filename */
		/* .protocol */			NULL,
		/* .cgienv */			NULL,
		/* .extra_mimetypes */		&extraMimes,
		/* .interpret */		NULL,
		/* .cgi_timeout */		0,
		/* .cache_max_age */		0,
		/* .auth_mask */		0,
		/* .cache_reusable */		0,
		/* .cache_revalidate */		0,
		/* .cache_intermediaries */	0,
		/* .origin_protocol */		LWSMPRO_CALLBACK,	/* files in a dir */
		/* .mountpoint_len */		0,		/* char count */
		/* .basic_auth_login_file */	NULL,
};

static struct lws_http_mount examplesMount = {
		/* .mount_next */		&examplesListMount,		/* linked-list "next" */
		/* .mountpoint */		NULL,		/* mountpoint URL */
		/* .origin */			"examples",		/* serve from dir */
		/* .def */			NULL,	/* default filename */
		/* .protocol */			NULL,
		/* .cgienv */			NULL,
		/* .extra_mimetypes */		&extraMimes,
		/* .interpret */		NULL,
		/* .cgi_timeout */		0,
		/* .cache_max_age */		0,
		/* .auth_mask */		0,
		/* .cache_reusable */		0,
		/* .cache_revalidate */		0,
		/* .cache_intermediaries */	0,
		/* .origin_protocol */		LWSMPRO_FILE,	/* files in a dir */
		/* .mountpoint_len */		0,		/* char count */
		/* .basic_auth_login_file */	NULL,
};

static struct lws_http_mount frontMount = {
		/* .mount_next */		&examplesMount,		/* linked-list "next" */
		/* .mountpoint */		NULL,		/* mountpoint URL */
		/* .origin */			"front",		/* serve from dir */
		/* .def */			"index.html",	/* default filename */
		/* .protocol */			NULL,
		/* .cgienv */			NULL,
		/* .extra_mimetypes */		NULL,
		/* .interpret */		NULL,
		/* .cgi_timeout */		0,
		/* .cache_max_age */		0,
		/* .auth_mask */		0,
		/* .cache_reusable */		0,
		/* .cache_revalidate */		0,
		/* .cache_intermediaries */	0,
		/* .origin_protocol */		LWSMPRO_FILE,	/* files in a dir */
		/* .mountpoint_len */		0,		/* char count */
		/* .basic_auth_login_file */	NULL,
};

struct luaAllocatorState_t {
	size_t maxSize;
	size_t used;
};

static void *luaAllocRestricted(void *ud, void *ptr, size_t osize, size_t nsize) {
	auto state = (luaAllocatorState_t*)ud;
	if (ptr == NULL) {
		/*
		 * <http://www.lua.org/manual/5.2/manual.html#lua_Alloc>:
		 * When ptr is NULL, osize encodes the kind of object that Lua is
		 * allocating.
		 *
		 * Since we don’t care about that, just mark it as 0.
		 */
		osize = 0;
	}
	if (nsize == 0) {
		free(ptr);
		state->used -= osize;
		return NULL;
	} else {
		if (state->used + (nsize - osize) > state->maxSize) {
			return NULL;
		}
		ptr = realloc(ptr, nsize);
		if (ptr) {
			state->used += nsize - osize;
		}
		return ptr;
	}
}

int main(int argc, char *argv[]) {
	if (argc != 4) {
		printf("Syntax: luasand <COM port> <HTTP port> <HTTP location>\n");
		exitProcess(1);
	}

	int httpPort = atoi(argv[2]);
	gSerialPort = openSerialPort(argv[1]);
	if (gSerialPort < 0) {
		exitProcess(1);
	}

	luaAllocatorState_t ud = {1024 * 1024, 0};
	gLuaState = lua_newstate(luaAllocRestricted, &ud);
	luaL_openlibs(gLuaState);

	lua_pushcfunction(gLuaState, lua_timestamp);
	lua_setglobal(gLuaState, "timestamp");
	lua_pushcfunction(gLuaState, lua_addcolor);
	lua_setglobal(gLuaState, "addcolor");
	lua_pushcfunction(gLuaState, lua_setcolor);
	lua_setglobal(gLuaState, "setcolor");

	lua_pushinteger(gLuaState, PIX_NUM);
	lua_setglobal(gLuaState, "PIX_NUM");
	lua_pushinteger(gLuaState, DELAY_MIN);
	lua_setglobal(gLuaState, "DELAY_MIN");
	lua_pushinteger(gLuaState, DELAY_MAX);
	lua_setglobal(gLuaState, "DELAY_MAX");
	lua_pushinteger(gLuaState, DELAY_FOREVER);
	lua_setglobal(gLuaState, "DELAY_FOREVER");

	if (luaL_dofile(gLuaState, "init.lua") != LUA_OK) {
		fprintf(stderr, "%s", lua_tostring(gLuaState, -1));
		exitProcess(2);
	}

	ud.maxSize = ud.used + 4 * 1024 * 1024;

	lws_context_creation_info info;
	memset(&info, 0, sizeof(info));
	info.port = httpPort;
	info.protocols = protocols;

	frontMount.mountpoint = argv[3];
	frontMount.mountpoint_len = strlen(argv[3]);

	auto examplesMountPoint = string(argv[3]) + "/examples";
	examplesMount.mountpoint = examplesMountPoint.c_str();
	examplesMount.mountpoint_len = examplesMountPoint.length();

	auto examplesListMountPoint = examplesMountPoint + "/list";
	examplesListMount.mountpoint = examplesListMountPoint.c_str();
	examplesListMount.mountpoint_len = examplesListMountPoint.length();

	info.mounts = &frontMount;
	info.gid = -1;
	info.uid = -1;

	struct lws_context *context = lws_create_context(&info);

	while (gRunning) {
		lws_service(context, 1000000);
	}

	lws_context_destroy(context);

	exitProcess(0);
}

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

using namespace std;

#define LUA_CODE_LEN (1024 * 1024 * 4)
#define WS_RX_BUFFER_BYTES (LUA_CODE_LEN + 1)

struct ClientData {
	ClientData()
		: luaCodeBufferSize(0)
	{

	}

	char luaCodeBuffer[LUA_CODE_LEN + 1];
	size_t luaCodeBufferSize;
};

unordered_map<lws*, ClientData> g_clientsData;
lua_State *L = nullptr;

// TODO: memory allocation limit
void runLuaSandboxed(const char *code) {
	lua_getglobal(L, "run_sandboxed");
	lua_pushstring(L, code);
	lua_call(L, 1, 2);
	if (lua_toboolean(L, -2)) {
		int len = (int) lua_rawlen(L, -1);
		uint8_t result[len];
		if (len > 0) {
			for (int i = 1; i <= len; i++) {
				lua_rawgeti(L, -1, i);
				result[i - 1] = (uint8_t) lua_tointeger(L, -1);
				lua_pop(L, 1);
			}
		}
	} else {
		const char *error = lua_tostring(L, -1);
		fprintf(stderr, "result is: %s\n", error);
	}
	lua_pop(L, 2);
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
		runLuaSandboxed(clientData.luaCodeBuffer);
		clientData.luaCodeBufferSize = 0;
		unsigned char r[] = {'s', 'c', 's', '\0'};
		lws_write(wsi, r, 4, LWS_WRITE_TEXT);
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

int main() {
	L = luaL_newstate();
	luaL_openlibs(L);

	if (luaL_dofile(L, "../init.lua") != LUA_OK) {
		fprintf(stderr, "%s", lua_tostring(L, -1));
		return 1;
	}

	if (luaL_dofile(L, "../test.lua") != LUA_OK) {
		fprintf(stderr, "%s", lua_tostring(L, -1));
		return 1;
	}

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

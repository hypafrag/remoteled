local BASE_ENV = {}

-- List of unsafe packages/functions:
--
-- * string.rep: can be used to allocate millions of bytes in 1 operation
-- * {set|get}metatable: can be used to modify the metatable of global objects (strings, integers)
-- * collectgarbage: can affect performance of other systems
-- * dofile: can access the server filesystem
-- * _G: It has access to everything. It can be mocked to other things though.
-- * load{file|string}: All unsafe because they can grant acces to global env
-- * raw{get|set|equal}: Potentially unsafe
-- * module|require|module: Can modify the host settings
-- * string.dump: Can display confidential server info (implementation of functions)
-- * math.randomseed: Can affect the host sytem
-- * io.*, os.*: Most stuff there is unsafe, see below for exceptions

RESULT_LEN = 300 * 3

RESULT_OFF = {}

for _=1, 300 do
	table.insert(RESULT_OFF, 0)
	table.insert(RESULT_OFF, 0)
	table.insert(RESULT_OFF, 0)
end

-- Safe packages/functions below
([[
RESULT_LEN RESULT_OFF
_VERSION assert error	ipairs   next pairs
pcall	select tonumber tostring type unpack xpcall
coroutine.create coroutine.resume coroutine.running coroutine.status
coroutine.wrap   coroutine.yield
math.abs   math.acos math.asin  math.atan math.atan2 math.ceil
math.cos   math.cosh math.deg   math.exp  math.fmod  math.floor
math.frexp math.huge math.ldexp math.log  math.log10 math.max
math.min   math.modf math.pi	math.pow  math.rad   math.random
math.sin   math.sinh math.sqrt  math.tan  math.tanh
os.clock os.difftime os.time
string.byte string.char  string.find  string.format string.gmatch
string.gsub string.len   string.lower string.match  string.reverse
string.sub  string.upper
table.insert table.maxn table.remove table.sort
]]):gsub('%S+', function(id)
	local module, method = id:match('([^%.]+)%.([^%.]+)')
	if module then
		BASE_ENV[module] = BASE_ENV[module] or {}
		BASE_ENV[module][method] = _G[module][method]
	else
		BASE_ENV[id] = _G[id]
	end
end)

local function protect_module(module, module_name)
	return setmetatable({}, {
		__index = module,
		__newindex = function(_, attr_name, _)
		error('Can not modify ' .. module_name .. '.' .. attr_name .. '. Protected by the sandbox.')
	end})
end

('coroutine math os string table'):gsub('%S+', function(module_name)
	BASE_ENV[module_name] = protect_module(BASE_ENV[module_name], module_name)
end)

local function is_byte_array(t)
	if type(t) ~= 'table' then
		return false
	end
	local i = 0
	for _ in pairs(t) do
		i = i + 1
		if t[i] == nil or not (t[i] >= 0 and t[i] <= 255) then
			return false
		end
	end
	return true
end

function run_sandboxed(untrusted_code)
	local untrusted_function, message = load(untrusted_code, nil, 't', BASE_ENV)
	if not untrusted_function then
		return false, message
	end
	success, result = pcall(untrusted_function)
	if not is_byte_array(result) then
		return false, 'Returned value is not a byte array'
	end
	if #result ~= RESULT_LEN then
		return false, string.format('Result length should be %d bytes, actual is %d', RESULT_LEN, #result)
	end
	return success, result
end

print('Sandbox loaded')

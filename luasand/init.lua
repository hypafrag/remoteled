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

RESULT_LEN = PIX_NUM * 3

-- TODO: reimplement in c, make config for calibrations
local function gammac(c, g, l, h)
	return math.ceil(math.pow(c / 0xff.0, g) * (h - l) + l)
end

function gamma(c, g)
	g = g or 6.0
	return	(gammac((c >> 16),       g, 0x00, 0x60) << 16) |
			(gammac((c >> 8) & 0xff, g, 0x01, 0x60) << 8) |
			 gammac((c & 0xff),      g, 0x01, 0x60)
end

-- Safe packages/functions below
([[
timestamp addcolor setcolor gamma
RESULT_LEN PIX_NUM DELAY_MIN DELAY_MAX DELAY_FOREVER
_VERSION assert error	ipairs   next pairs
pcall	select tonumber tostring type xpcall
coroutine.create coroutine.resume coroutine.running coroutine.status
coroutine.wrap   coroutine.yield
bit32.arshift bit32.band    bit32.bnot    bit32.bor    bit32.btest
bit32.bxor    bit32.extract bit32.lrotate bit32.lshift bit32.replace
bit32.rrotate bit32.rshift
math.abs   math.acos math.asin  math.atan math.atan2 math.ceil
math.cos   math.cosh math.deg   math.exp  math.fmod  math.floor
math.frexp math.huge math.ldexp math.log  math.log10 math.max
math.min   math.modf math.pi	math.pow  math.rad   math.random
math.sin   math.sinh math.sqrt  math.tan  math.tanh
os.clock os.difftime os.time os.date
string.byte string.char  string.find  string.format string.gmatch
string.gsub string.len   string.lower string.match  string.reverse
string.sub  string.upper
table.insert table.maxn table.remove table.sort table.unpack
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
			print(module_name, attr_name)
			error('Can not modify ' .. module_name .. '.' .. attr_name .. '. Protected by the sandbox.')
		end
	})
end

('coroutine math os string table bit32'):gsub('%S+', function(module_name)
	BASE_ENV[module_name] = protect_module(BASE_ENV[module_name], module_name)
end)

BASE_ENV_PROTECTED = protect_module(BASE_ENV, '_G')

local function to_frame_buffer(result)
	if type(result) == 'number' then
		if result < 0 or result > 0xffffff then
			return nil, 'Number result should be in range [0x000000, 0xffffff]'
		end
		local r = result >> 16
		local g = (result >> 8) & 0xff
		local b = result & 0xff
		result = {}
		for _ = 1, PIX_NUM do
			table.insert(result, r)
			table.insert(result, g)
			table.insert(result, b)
		end
		return result, nil
	end
	if type(result) == 'table' then
		if #result ~= RESULT_LEN then
			return nil, string.format('Result length should be %d bytes, actual is %d', RESULT_LEN, #result)
		end
		local i = 0
		for _ in pairs(result) do
			i = i + 1
			if result[i] == nil then
				return nil, 'Returned table is not a byte array. ' ..
					string.format('Element %i is missing', i)
			end
			if not (result[i] >= 0 and result[i] <= 255) then
				return nil, 'Returned table is not a byte array. ' ..
					string.format('Element %i is %s of type %s. Should be [0..255]',
						i, tostring(t[i]), type(result[i]))
			end
		end
		return result, nil
	end
	return nil, 'Returned value is not a byte array'
end

function run_sandboxed(untrusted_code, code_type, state)
	BASE_ENV['STATE'] = state
	local untrusted_function, message = load(untrusted_code, nil, code_type, BASE_ENV_PROTECTED)
	if not untrusted_function then
		return false, message, nil, nil
	end
	local success, result, delay, state = pcall(untrusted_function)
	BASE_ENV['STATE'] = nil
	collectgarbage("collect")
	if success then
		delay = delay or DELAY_FOREVER
		if delay < DELAY_MIN then
			return false, 'Delay shouldn\'t be less then ' .. DELAY_MIN, nil, nil
		end
		if delay > DELAY_MAX and delay ~= DELAY_FOREVER then
			return false, 'Delay shouldn\'t be more then ' .. DELAY_MAX, nil, nil
		end
		local message
		result, message = to_frame_buffer(result)
		if result == nil then
			return false, message, nil, nil
		end
	end
	return success, result, delay, state
end

print('Sandbox loaded')

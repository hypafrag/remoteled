-- -- Gradient function finds dot product between pseudorandom gradient vector
-- -- and the vector from input coordinate to a unit cube vertex
-- local dot_product = {
-- 	[0x0]=function(x,y,z) return  x + y end,
-- 	[0x1]=function(x,y,z) return -x + y end,
-- 	[0x2]=function(x,y,z) return  x - y end,
-- 	[0x3]=function(x,y,z) return -x - y end,
-- 	[0x4]=function(x,y,z) return  x + z end,
-- 	[0x5]=function(x,y,z) return -x + z end,
-- 	[0x6]=function(x,y,z) return  x - z end,
-- 	[0x7]=function(x,y,z) return -x - z end,
-- 	[0x8]=function(x,y,z) return  y + z end,
-- 	[0x9]=function(x,y,z) return -y + z end,
-- 	[0xA]=function(x,y,z) return  y - z end,
-- 	[0xB]=function(x,y,z) return -y - z end,
-- 	[0xC]=function(x,y,z) return  y + x end,
-- 	[0xD]=function(x,y,z) return -y + z end,
-- 	[0xE]=function(x,y,z) return  y - x end,
-- 	[0xF]=function(x,y,z) return -y - z end
-- }
--
-- local function grad(hash, x, y, z)
-- 	return dot_product[bit32.band(hash,0xF)](x,y,z)
-- end
--
-- -- Fade function is used to smooth final output
-- local function perlin_fade(t)
-- 	return t * t * t * (t * (t * 6 - 15) + 10)
-- end
--
-- local function lerp(t, a, b)
-- 	return a + t * (b - a)
-- end
--
-- -- Hash lookup table as defined by Ken Perlin
-- -- This is a randomly arranged array of all numbers from 0-255 inclusive
-- local perlin_permutation = {151,160,137,91,90,15,
-- 	131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,
-- 	190, 6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,
-- 	88,237,149,56,87,174,20,125,136,171,168, 68,175,74,165,71,134,139,48,27,166,
-- 	77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,
-- 	102,143,54, 65,25,63,161, 1,216,80,73,209,76,132,187,208, 89,18,169,200,196,
-- 	135,130,116,188,159,86,164,100,109,198,173,186, 3,64,52,217,226,250,124,123,
-- 	5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,
-- 	223,183,170,213,119,248,152, 2,44,154,163, 70,221,153,101,155,167, 43,172,9,
-- 	129,22,39,253, 19,98,108,110,79,113,224,232,178,185, 112,104,218,246,97,228,
-- 	251,34,242,193,238,210,144,12,191,179,162,241, 81,51,145,235,249,14,239,107,
-- 	49,192,214, 31,181,199,106,157,184, 84,204,176,115,121,50,45,127, 4,150,254,
-- 	138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180
-- }
--
-- local perlin_permutation_buffer = {}
--
-- -- p is used to hash unit cube coordinates to [0, 255]
-- for i = 0,255 do
-- 	-- Convert to 0 based index table
-- 	perlin_permutation_buffer[i] = perlin_permutation[i+1]
-- 	-- Repeat the array to avoid buffer overflow in hash function
-- 	perlin_permutation_buffer[i+256] = perlin_permutation[i+1]
-- end
--
-- -- Return range: [-1, 1]
-- local function perlin(x, y, z)
-- 	y = y or 0
-- 	z = z or 0
--
-- 	-- Calculate the "unit cube" that the point asked will be located in
-- 	local xi = bit32.band(math.floor(x),255)
-- 	local yi = bit32.band(math.floor(y),255)
-- 	local zi = bit32.band(math.floor(z),255)
--
-- 	-- Next we calculate the location (from 0 to 1) in that cube
-- 	x = x - math.floor(x)
-- 	y = y - math.floor(y)
-- 	z = z - math.floor(z)
--
-- 	-- We also fade the location to smooth the result
-- 	local u = perlin_fade(x)
-- 	local v = perlin_fade(y)
-- 	local w = perlin_fade(z)
--
-- 	-- Hash all 8 unit cube coordinates surrounding input coordinate
-- 	local p = perlin_permutation_buffer
-- 	local A, AA, AB, AAA, ABA, AAB, ABB, B, BA, BB, BAA, BBA, BAB, BBB
-- 	A   = p[xi  ] + yi
-- 	AA  = p[A   ] + zi
-- 	AB  = p[A+1 ] + zi
-- 	AAA = p[ AA ]
-- 	ABA = p[ AB ]
-- 	AAB = p[ AA+1 ]
-- 	ABB = p[ AB+1 ]
--
-- 	B   = p[xi+1] + yi
-- 	BA  = p[B   ] + zi
-- 	BB  = p[B+1 ] + zi
-- 	BAA = p[ BA ]
-- 	BBA = p[ BB ]
-- 	BAB = p[ BA+1 ]
-- 	BBB = p[ BB+1 ]
--
-- 	-- Take the weighted average between all 8 unit cube coordinates
-- 	return lerp(w,
-- 		lerp(v,
-- 			lerp(u,
-- 				grad(AAA, x, y, z),
-- 				grad(BAA, x-1, y, z)
-- 			),
-- 			lerp(u,
-- 				grad(ABA, x, y-1, z),
-- 				grad(BBA, x-1, y-1, z)
-- 			)
-- 		),
-- 		lerp(v,
-- 			lerp(u,
-- 				grad(AAB, x, y, z - 1), grad(BAB, x-1, y, z-1)
-- 			),
-- 			lerp(u,
-- 				grad(ABB, x, y-1, z-1), grad(BBB, x-1, y-1, z-1)
-- 			)
-- 		)
-- 	)
-- end

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

local function gamma(c, g)
	g = g or 6.0
	return	(gammac((c >> 16),	   g, 0x00, 0x60) << 16) |
			(gammac((c >> 8) & 0xff, g, 0x01, 0x60) << 8) |
			 gammac((c & 0xff),	  g, 0x01, 0x60)
end

_G['gamma'] = gamma
_G['perlin'] = perlin
_G['lerp'] = lerp

-- Safe packages/functions below
;([[
timestamp addcolor setcolor gamma perlin lerp
RESULT_LEN PIX_NUM DELAY_MIN DELAY_MAX DELAY_FOREVER
_VERSION assert error ipairs   next pairs
pcall select tonumber tostring type xpcall
coroutine.create coroutine.resume coroutine.running coroutine.status
coroutine.wrap   coroutine.yield
bit32.arshift bit32.band  bit32.bnot    bit32.bor    bit32.btest
bit32.bxor	bit32.extract bit32.lrotate bit32.lshift bit32.replace
bit32.rrotate bit32.rshift
math.abs   math.acos math.asin  math.atan math.atan2 math.ceil
math.cos   math.cosh math.deg   math.exp  math.fmod  math.floor
math.frexp math.huge math.ldexp math.log  math.log10 math.max
math.min   math.modf math.pi    math.pow  math.rad   math.random
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

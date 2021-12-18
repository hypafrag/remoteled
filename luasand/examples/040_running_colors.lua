-- running colors

local result = {}
local pc = STATE or 0
local third = PIX_NUM / 3
local rfocus = pc % PIX_NUM
local gfocus = (pc + third) % PIX_NUM
local bfocus = (pc + third * 2) % PIX_NUM

local function color(focus, i)
	local rdistance = math.abs(i - focus)
	local ldistance = PIX_NUM - rdistance
	return math.floor(255 / (math.min(rdistance, ldistance) + 1))
end

for i = 0, PIX_NUM - 1 do
	table.insert(result, color(rfocus, i)) -- red
	table.insert(result, color(gfocus, i)) -- green
	table.insert(result, color(bfocus, i)) -- blue
end

return result, DELAY_MIN, pc + 1

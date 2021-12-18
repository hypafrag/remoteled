-- running colors

local PERIOD_COUNTER = STATE or 0
local result = {}
local third = PIX_NUM / 3
local rfocus = PERIOD_COUNTER % PIX_NUM
local gfocus = (PERIOD_COUNTER + third) % PIX_NUM
local bfocus = (PERIOD_COUNTER + third * 2) % PIX_NUM

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

PERIOD_COUNTER = PERIOD_COUNTER + 1
return result, DELAY_MIN, PERIOD_COUNTER

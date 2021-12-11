-- fast running colors ping pong (hypnofrog)

local result = {}
local third = PIX_NUM / 3
local phase = PERIOD_COUNTER * 16
phase = phase % (PIX_NUM * 2)
if phase > PIX_NUM then
	phase = PIX_NUM - (phase - PIX_NUM)
end
local rfocus = phase % PIX_NUM
local gfocus = (phase + third) % PIX_NUM
local bfocus = (phase + third * 2) % PIX_NUM

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

return result, 40

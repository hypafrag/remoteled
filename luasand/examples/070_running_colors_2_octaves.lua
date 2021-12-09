-- running colors 2 octaves

local result = {}
local third = PIX_NUM / 3
local phase = PERIOD_COUNTER
phase = phase % (PIX_NUM * 2)
if phase > PIX_NUM then
	phase = PIX_NUM - (phase - PIX_NUM)
end
local rfocus1 = phase % PIX_NUM
local gfocus1 = (phase + third) % PIX_NUM
local bfocus1 = (phase + third * 2) % PIX_NUM

phase = PIX_NUM - phase

local bfocus2 = phase % PIX_NUM
local gfocus2 = (phase + third) % PIX_NUM
local rfocus2 = (phase + third * 2) % PIX_NUM

local function color(focus, i)
	local rdistance = math.abs(i - focus)
	local ldistance = PIX_NUM - rdistance
	return math.floor(255 / (math.min(rdistance, ldistance) + 1))
end

local chunklen = 10
local offset = PERIOD_COUNTER % (chunklen * 2) - chunklen

for i = 0, PIX_NUM - 1 do
	if (i + offset) % (chunklen * 2) > chunklen - 1 then
		table.insert(result, color(rfocus1, i)) -- red
		table.insert(result, color(gfocus1, i)) -- green
		table.insert(result, color(bfocus1, i)) -- blue
	else
		table.insert(result, color(rfocus2, i)) -- red
		table.insert(result, color(gfocus2, i)) -- green
		table.insert(result, color(bfocus2, i)) -- blue
	end
end

return result, DELAY_MIN

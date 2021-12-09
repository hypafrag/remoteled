-- running colors and gaps 3 octaves

local result = {}
local third = PIX_NUM / 3

local phase12 = PERIOD_COUNTER
phase12 = phase12 % (PIX_NUM * 2)
if phase12 > PIX_NUM then
	phase12 = PIX_NUM - (phase12 - PIX_NUM)
end
local rfocus1 = phase12 % PIX_NUM
local gfocus1 = (phase12 + third) % PIX_NUM
local bfocus1 = (phase12 + third * 2) % PIX_NUM

phase12 = PIX_NUM - phase12

local bfocus2 = phase12 % PIX_NUM
local gfocus2 = (phase12 + third) % PIX_NUM
local rfocus2 = (phase12 + third * 2) % PIX_NUM

local function color(focus, i)
	local rdistance = math.abs(i - focus)
	local ldistance = PIX_NUM - rdistance
	return math.floor(255 / (math.min(rdistance, ldistance) + 1))
end

local chunklen2 = 10
local offset2 = PERIOD_COUNTER % (chunklen2 * 2) - chunklen2

local gap3 = 2
local step3 = 1 -- [-gap3 .. gap3]
local speed3 = 0.6 -- (0 .. 1.0]

local offset3 = gap3 + 1
local phase3 = (math.floor(PERIOD_COUNTER * speed3) * (offset3 + step3)) % offset3

for i = 0, PIX_NUM - 1 do
    if i % offset3 == phase3 then
    	if (i + offset2) % (chunklen2 * 2) > chunklen2 - 1 then
    		table.insert(result, color(rfocus1, i)) -- red
    		table.insert(result, color(gfocus1, i)) -- green
    		table.insert(result, color(bfocus1, i)) -- blue
    	else
    		table.insert(result, color(rfocus2, i)) -- red
    		table.insert(result, color(gfocus2, i)) -- green
    		table.insert(result, color(bfocus2, i)) -- blue
    	end
	else
	    addcolor(result, 0x000000)
    end
end

return result, DELAY_MIN

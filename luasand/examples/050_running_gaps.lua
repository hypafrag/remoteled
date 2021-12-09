-- running gaps

local result = {}

local gap = 2
local step = -1  -- [-gap .. gap]
local speed = 0.6 -- (0 .. 1.0]

local offset = gap + 1
local phase = (math.floor(PERIOD_COUNTER * speed) * (offset + step)) % offset

for i = 1, PIX_NUM do
	if i % offset == phase then
		table.insert(result, math.random(0x00, 0x0f)) -- red
		table.insert(result, math.random(0x00, 0x0f)) -- green
		table.insert(result, math.random(0x00, 0x0f)) -- blue
	else
		addcolor(result, 0x000000)
	end
end

return result, 100

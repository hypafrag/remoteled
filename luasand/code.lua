result = {}
for i = 1, 300, 1 do
    table.insert(result, math.random(0x00, 0x0f)) -- red
    table.insert(result, math.random(0x00, 0x0f)) -- green
    table.insert(result, math.random(0x00, 0x0f)) -- blue
end

return result, 200

--

local result = {}
local rfocus = PERIOD_COUNTER % 300
local gfocus = (PERIOD_COUNTER + 100) % 300
local bfocus = (PERIOD_COUNTER + 200) % 300
for i = 1, 300, 1 do
	table.insert(result, math.floor(255 / (math.abs(i - rfocus) + 1))) -- red
	table.insert(result, math.floor(255 / (math.abs(i - gfocus) + 1))) -- green
	table.insert(result, math.floor(255 / (math.abs(i - bfocus) + 1))) -- blue
end

return result, 50

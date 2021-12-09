-- dim random flashing

local result = {}

for i = 1, PIX_NUM do
	table.insert(result, math.random(0x00, 0x0f)) -- red
	table.insert(result, math.random(0x00, 0x0f)) -- green
	table.insert(result, math.random(0x00, 0x0f)) -- blue
end

return result, 200

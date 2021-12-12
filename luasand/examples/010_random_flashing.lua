-- random flashing

local result = {}

for i = 1, PIX_NUM do
	addcolor(result, gamma(math.random(0x000000, 0xffffff)))
end

return result, 100

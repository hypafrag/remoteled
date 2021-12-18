-- sonar scope

local result = {}
local pc = STATE or 0

local offset = 54
local lens = { 28, 25, 24, 23, 22, 20, 18, 17, 16, 15, 14, 13 }

local rings = {}
local posstart = offset
for i = 1, #lens do
	local posend = posstart + lens[i]
	table.insert(rings, { posstart, posend })
	posstart = posend + 1
end

local ringi = #rings - pc % #rings
local posstart, posend = table.unpack(rings[ringi])
local pingled = 198
local pingring = 5

for i = 1, PIX_NUM do
	if i == pingled then
		local distance = #rings - ringi + pingring
		if ringi <= pingring then
			distance = distance - #rings
		end
		local f = 1.0 - distance / #rings
		f = f * f
		addcolor(result, 0x000100 * math.floor(f * 160))
	elseif i >= posstart and i <= posend then
		addcolor(result, 0x000800)
	else
		addcolor(result, 0x000000)
	end
end

return result, 80, pc + 1

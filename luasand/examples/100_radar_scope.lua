-- radar scope

local result = {}
for i = 1, PIX_NUM do
	addcolor(result, 0x000000)
end

local offset = 54
local lens = { 28, 25, 24, 23, 22, 20, 18, 17, 16, 15, 14, 13 }
local angles = { 165.0, 140.0, 140.0, 135.0, 110.0, 90.0, 85.0, 85.0, 80.0, 70.0, 65.0, 45.0 }

local rings = {}
local posstart = offset
for i = 1, #lens do
	local posend = posstart + lens[i]
	table.insert(rings, { posstart, posend })
	posstart = posend + 1
end

local anglesteps = {}
for i = 1, #lens do
	table.insert(anglesteps, 360.0 / lens[i])
end

local threshold = 10.0
local beamazimuth = (PERIOD_COUNTER * 10 + PERIOD_COUNTER / 360) % 360
local pingazimuth = 130.0
local pingduration = 200.0
local pingindex = 198
local pingintensity = 200.0

if beamazimuth > pingazimuth and beamazimuth < pingazimuth + pingduration then
	local f = 1.0 - (beamazimuth - pingazimuth) / pingduration
	f = f * f
	setcolor(result, pingindex, math.floor(f * pingintensity) * 0x100)
end

for i = 1, #angles do
	local angle = angles[i]
	local azimuth = beamazimuth
	if angle > azimuth then
		azimuth = azimuth + 360.0
	end
	local anglestep = anglesteps[i]
	local posstart, posend = table.unpack(rings[i])

	local mindiff = 1000.0
	local selectedpos = 0

	for j = posend, posstart, -1 do
		local diff = math.abs(azimuth - angle)
		if diff < mindiff then
			mindiff = diff
			selectedpos = j
		end
		angle = angle + anglestep
	end

	if mindiff < threshold then
		local intensity = math.floor(((threshold - mindiff) / threshold) * 30)
		result[(selectedpos - 1) * 3 + 2] = intensity;
	end
end

return result, 40

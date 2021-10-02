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

--

-- running colors
local result = {}
local rfocus = PERIOD_COUNTER % 300
local gfocus = (PERIOD_COUNTER + 100) % 300
local bfocus = (PERIOD_COUNTER + 200) % 300


for i = 0, 299, 1 do
	table.insert(result, math.floor(255 /
	    (math.min(math.abs(i - rfocus), 300 - math.abs(i - rfocus)) + 1))) -- red
	table.insert(result, math.floor(255 /
	    (math.min(math.abs(i - gfocus), 300 - math.abs(i - gfocus)) + 1))) -- green
	table.insert(result, math.floor(255 /
	    (math.min(math.abs(i - bfocus), 300 - math.abs(i - bfocus)) + 1))) -- blue
end
return result, 50

--

-- running colors
local result = {}
local rfocus = PERIOD_COUNTER % 300
local gfocus = (PERIOD_COUNTER + 100) % 300
local bfocus = (PERIOD_COUNTER + 200) % 300

function color(focus, i)
    local rdistance = math.abs(i - focus)
    local ldistance = 300 - rdistance
    return math.floor(255 / (math.min(rdistance, ldistance) + 1))
end

for i = 0, 299, 1 do
	table.insert(result, color(rfocus, i)) -- red
	table.insert(result, color(gfocus, i)) -- green
	table.insert(result, color(bfocus, i)) -- blue
end

return result, 50

--

-- smooth running colors ping pong
local result = {}
local third = PIX_NUM / 3
local phase = PERIOD_COUNTER + 301
phase = phase % (PIX_NUM * 2)
if phase > PIX_NUM then
    phase = PIX_NUM - (phase - PIX_NUM)
end
local rfocus = phase % PIX_NUM
local gfocus = (phase + third) % PIX_NUM
local bfocus = (phase + third * 2) % PIX_NUM

function color(focus, i)
    local rdistance = math.abs(i - focus)
    local ldistance = PIX_NUM - rdistance
    return math.floor(255 / (math.min(rdistance, ldistance) + 1))
end

for i = 0, PIX_NUM - 1, 1 do
	table.insert(result, color(rfocus, i)) -- red
	table.insert(result, color(gfocus, i)) -- green
	table.insert(result, color(bfocus, i)) -- blue
end

return result, 50

--

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

function color(focus, i)
    local rdistance = math.abs(i - focus)
    local ldistance = PIX_NUM - rdistance
    return math.floor(255 / (math.min(rdistance, ldistance) + 1))
end

for i = 0, PIX_NUM - 1, 1 do
	table.insert(result, color(rfocus, i)) -- red
	table.insert(result, color(gfocus, i)) -- green
	table.insert(result, color(bfocus, i)) -- blue
end

return result, DELAY_MIN

--

-- smooth running colors ping pong 2 octaves
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

function color(focus, i)
    local rdistance = math.abs(i - focus)
    local ldistance = PIX_NUM - rdistance
    return math.floor(255 / (math.min(rdistance, ldistance) + 1))
end

local chunklen = 10
local offset = PERIOD_COUNTER % (chunklen * 2) - chunklen

for i = 0, PIX_NUM - 1, 1 do
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

--

function pushcolor(c)
    local r = math.floor(c / 0x10000)
    local g = math.floor((c - r * 0x10000) / 0x100)
    local b = c % 0x100
    table.insert(result, r)
    table.insert(result, g)
    table.insert(result, b)
end

--

-- coil concentric pulse

local result = {}
local lens = { 54, 28, 25, 24, 23, 22, 20, 18, 17, 16, 15, 14, 13 }
local angles = { 165, 140, 140, 135, 110, 90, 85, 85, 80, 70, 65, 45  }

local cases = {}
local posstart = lens[1]
for i = 2, #lens do
    local posend = posstart + lens[i]
    table.insert(cases, { posstart, posend })
    posstart = posend + 1
end

local posstart, posend = table.unpack(cases[13])

for i = 1, PIX_NUM do
    if i == posstart then
        addcolor(result, 0x001100)
    else
        addcolor(result, 0x000000)
    end
end

return result, DELAY_MIN

--

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
local pingduration = 140.0
local pingindex = 198
local pingintensity = 10.0

if beamazimuth > pingazimuth and beamazimuth < pingazimuth + pingduration then
    local f = 1.0 - (beamazimuth - pingazimuth) / pingduration
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

return result, DELAY_MIN

--

-- running colors with reverse running gaps

local result = {}
local third = PIX_NUM / 3
local rfocus = PERIOD_COUNTER % PIX_NUM
local gfocus = (PERIOD_COUNTER + third) % PIX_NUM
local bfocus = (PERIOD_COUNTER + third * 2) % PIX_NUM

local gap = 2
local step = -1
local speed = 0.5

local offset = gap + 1
local phase = ((math.floor(PERIOD_COUNTER * speed)) * (offset + step)) % offset

function color(focus, i)
    local rdistance = math.abs(i - focus)
    local ldistance = PIX_NUM - rdistance
    return math.floor(255 / (math.min(rdistance, ldistance) + 1))
end

for i = 0, PIX_NUM - 1 do
    if i % offset == phase then
    	table.insert(result, color(rfocus, i)) -- red
    	table.insert(result, color(gfocus, i)) -- green
    	table.insert(result, color(bfocus, i)) -- blue
	else
	    addcolor(result, 0x000000)
    end
end

return result, DELAY_MIN


--

-- -- running colors with reverse running gaps

-- local result = {}
-- local third = PIX_NUM / 3
-- local rfocus = PERIOD_COUNTER % PIX_NUM
-- local gfocus = (PERIOD_COUNTER + third) % PIX_NUM
-- local bfocus = (PERIOD_COUNTER + third * 2) % PIX_NUM

-- local gap = 2
-- local step = -1
-- local speed = 0.5

-- local offset = gap + 1
-- local phase = ((math.floor(PERIOD_COUNTER * speed)) * (offset + step)) % offset

-- local function color(focus, i)
--     local rdistance = math.abs(i - focus)
--     local ldistance = PIX_NUM - rdistance
--     return math.floor(255 / (math.min(rdistance, ldistance) + 1))
-- end

-- for i = 0, PIX_NUM - 1 do
--     if i % offset == phase then
--     	table.insert(result, color(rfocus, i)) -- red
--     	table.insert(result, color(gfocus, i)) -- green
--     	table.insert(result, color(bfocus, i)) -- blue
-- 	else
-- 	    addcolor(result, 0x000000)
--     end
-- end

-- return result, DELAY_MIN

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

local gap3 = 4
local step3 = 4 -- [-gap3 .. gap3]
local speed3 = 0.1 -- (0 .. 1.0]

local offset3 = gap3 + 1
local phase3 = (math.floor(PERIOD_COUNTER * speed3) * (offset3 + step3)) % offset3


for i = 0, PIX_NUM - 1 do
    if i % offset3 == phase3 then
    	if (i + offset) % (chunklen * 2) > chunklen - 1 then
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

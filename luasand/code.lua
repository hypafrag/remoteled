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

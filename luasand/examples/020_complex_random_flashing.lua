-- complex random flashing

local result = {}

local GAMMA = 2.2
local OFFSET_LEN = 0
local CHUNK_LEN = 3
local GAP_LEN = 1
local MIN_COLOR = 0x0f0f0f
-- local MAX_COLOR = 0x1f1f1f
-- local MAX_COLOR = 0x3f3f3f
local MAX_COLOR = 0x7f7f7f
-- local MAX_COLOR = 0xffffff

local function gamma(c, g)
    return math.floor(math.pow(c / 0xff.0, g) * 0xff)
end

local function gamma3(c, g)
    return
        (gamma(c >> 16, g) << 16) |
        (gamma((c >> 8) & 0xff, g) << 8) |
        gamma(c & 0xff, g)
end

for i = 1, OFFSET_LEN do
    addcolor(result, 0x000000)
end

for i = OFFSET_LEN + 1, PIX_NUM, CHUNK_LEN + GAP_LEN do
    local color = math.random(0x000000, 0xffffff)
    color = color | MIN_COLOR
    color = color & MAX_COLOR
    color = gamma3(color, GAMMA)
    local chunkstart = i
    local gapstart = chunkstart + CHUNK_LEN
    local nextchunkstart = gapstart + GAP_LEN
    for j = chunkstart, math.min(gapstart - 1, PIX_NUM) do
	    addcolor(result, color)
	end
    for j = gapstart, math.min(nextchunkstart - 1, PIX_NUM) do
	    addcolor(result, 0x000000)
	end
end

return result, 200

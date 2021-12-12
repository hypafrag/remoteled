-- complex random flashing

local result = {}

local OFFSET_LEN = 0
local CHUNK_LEN = 3
local GAP_LEN = 1
local MIN_COLOR = 0x000000
local MAX_COLOR = 0xffffff

for i = 1, OFFSET_LEN do
    addcolor(result, 0x000000)
end

for i = OFFSET_LEN + 1, PIX_NUM, CHUNK_LEN + GAP_LEN do
    local color = gamma((math.random(0x000000, 0xffffff)
        | MIN_COLOR)
        & MAX_COLOR)
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

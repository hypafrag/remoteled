-- epilepsy

local result = {}

local CHUNK_LEN = 100
local MIN_COLOR = 0x7f7f7f
local MAX_COLOR = 0xffffff

for i = 1, PIX_NUM, CHUNK_LEN do
    local color = gamma((math.random(0x000000, 0xffffff)
        | MIN_COLOR)
        & MAX_COLOR)
    for j = i, math.min(i + CHUNK_LEN - 1, PIX_NUM) do
	    addcolor(result, color)
	end
end

return result, DELAY_MIN

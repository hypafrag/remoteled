-- segmented

local result = {}

local LEFT_LEN = 100
local RIGHT_LEN = 80
local SKIP_LEN = 62
local DOWN_LEN = 58

for i = 1, DOWN_LEN do
    addcolor(result, 0x000000)
end

for i = 1, SKIP_LEN do
    addcolor(result, 0x000066)
end

for i = 1, RIGHT_LEN do
    addcolor(result, 0x0000ff)
end

for i = 1, LEFT_LEN do
    addcolor(result, 0xff0000)
end

return result

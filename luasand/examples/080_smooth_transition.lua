-- smooth transitions

local base = 0
local pc = PERIOD_COUNTER * 10
local singlecycle = 255
local fullcycle = singlecycle * 3

local rphase = pc % fullcycle
local gphase = (pc + singlecycle) % fullcycle
local bphase = (pc + singlecycle + singlecycle) % fullcycle

local r = math.max(singlecycle - math.abs(singlecycle - rphase), base)
local g = math.max(singlecycle - math.abs(singlecycle - gphase), base)
local b = math.max(singlecycle - math.abs(singlecycle - bphase), base)

return r << 16 | g << 8 | b, 60

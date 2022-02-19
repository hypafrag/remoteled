-- running colors perlin

local result = {}
local state = STATE or { {
        offset = 0.0,
        step = 0.02,
        octave = 0.01,
        power = 4,
        factor = 1,
    }, {
        offset = 0.6,
        step = 0.025,
        octave = 0.01,
        power = 4,
        factor = 1,
    }, {
        offset = 0.3,
        step = 0.03,
        octave = 0.01,
        power = 4,
        factor = 1,
    }
}

for i = 1, PIX_NUM do
    for _, cstate in ipairs(state) do
        local p = perlin(cstate.octave * i + cstate.offset, cstate.offset)
        local nc = math.pow((p + 1.0) * 0.5, cstate.power) * cstate.factor
        local c = math.floor(nc * 255)
        table.insert(result, c)
    end
end

for _, cstate in ipairs(state) do
    cstate.offset = cstate.offset + cstate.step
end

return result, 60, state

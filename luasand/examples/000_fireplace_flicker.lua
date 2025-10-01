-- fireplace flicker

local result = {}
local state = STATE or {
    offset = 0.0,
    step = 0.03,
    components = {{
        offset = 0.33,
        step = -0.025,
        octave = 0.02,
        bitoffset = 8,
        factor = 0.8,
    }, {
        offset = 0.33,
        step = -0.025,
        octave = 0.02,
        bitoffset = 16,
        factor = 1.0,
    }}
}

for i = 1, PIX_NUM do
    local color = 0
    for _, cstate in ipairs(state.components) do
        local p = perlin(cstate.octave * i + cstate.offset, state.offset)
        local nc = math.pow(((p + 1.0) * 0.5 * 0.8 + 0.2) * cstate.factor, 4.0)
        local c = math.floor(math.min(nc * 0xff, 0xff))
        color = color | c << cstate.bitoffset
    end
    addcolor(result, color)
end

for _, cstate in ipairs(state.components) do
    cstate.offset = cstate.offset + cstate.step
end
state.offset = state.offset + state.step

return result, 20, state

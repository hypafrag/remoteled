-- running colors perlin

local result = {}
local state = STATE or {
    offset = 0.0,
    step = 0.03,
    components = {{
        offset = 0.0,
        step = 0.02,
        octave = 0.02,
        bitoffset = 0,
    }, {
        offset = 0.33,
        step = -0.025,
        octave = 0.02,
        bitoffset = 8,
    }, {
        offset = 0.66,
        step = 0.03,
        octave = 0.02,
        bitoffset = 16,
    }}
}

for i = 1, PIX_NUM do
    local color = 0
    for _, cstate in ipairs(state.components) do
        local p = perlin(cstate.octave * i + cstate.offset, state.offset)
        local nc = math.pow((p + 1.0) * 0.5, 4.0)
        local c = math.floor(math.min(nc * 0xff, 0xff))
        color = color | c << cstate.bitoffset
    end
    addcolor(result, color)
end

for _, cstate in ipairs(state.components) do
    cstate.offset = cstate.offset + cstate.step
end
state.offset = state.offset + state.step

return result, 60, state

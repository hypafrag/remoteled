assert(not run_sandboxed [[
	print(2)
	return RESULT_OFF
]]) --> fails
assert(not run_sandboxed [[
	return {300, 300, 300}
]]) --> fails
assert(run_sandboxed [[
	x=1
	return RESULT_OFF
]]) --> ok

print('Sandbox tested')

from pathlib import Path
from types import SimpleNamespace
import numpy as np
from run_pte_experiments import bounds, expand, reverse_check, optimize, millis

args = SimpleNamespace(max_edges=10000, max_states=10000, preprocess_limit=10)
data = {'nodes': ['O', 'X', 'D'],
        'arcs': [(0, 0, 2, 5, 2000), (1, 0, 1, 20, 1000), (2, 1, 2, 20, 2000)],
        'commodities': [('K0', 0, 2, 5, 2000), ('K1', 0, 2, 5, 3000), ('K2', 2, 2, 3, 3000)],
        'costs': np.array([[2, 2, 2], [2, 2, 2], [2, 2, 2]], dtype=float)}
indices = [0, 1, 2]
outgoing, distances, _, _, _ = bounds(data, indices)
results = []
for pruned in [False, True]:
    stats, g = expand(data, indices, outgoing, distances, pruned, 10000, 10000, 10)
    assert stats['status'] == 'complete'
    if pruned:
        assert reverse_check(g)['backward_removed_states'] == 0
    result = optimize(data, indices, g, 10, Path('/tmp/pte_check.log'))
    assert result['lp_status'] == 'Optimal', result
    assert abs(result['objective'] - 30) < 1e-7, result
    assert result['max_demand_residual'] < 1e-7
    assert result['max_capacity_violation'] < 1e-7
    results.append(result)
data['arcs'][0] = (0, 0, 2, 4, 2000)
stats, g = expand(data, indices, outgoing, distances, True, 10000, 10000, 10)
result = optimize(data, indices, g, 10, Path('/tmp/pte_check_infeasible.log'))
assert result['lp_status'] == 'Infeasible'
assert millis(4.096) == 4096
try:
    millis(4.0961)
except ValueError:
    pass
else:
    raise AssertionError('Inexact scaling accepted')
print('PASS: exact deadlines, shared capacity, same-origin demand, baseline equivalence, infeasibility and decimal scaling')

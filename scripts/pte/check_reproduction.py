"""Check entrypoint paths and complete-count handling on a tiny temporary instance."""
import copy
import json
from pathlib import Path
import pickle
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from count_records import is_complete_count, read_complete_count

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run_heuristics
import run_ga_retune


def main():
    assert run_heuristics.DATA == ROOT / 'data' / 'processed'
    assert run_heuristics.OUT == ROOT / 'results' / 'generated' / 'heuristics'
    assert run_ga_retune.OUT == run_heuristics.OUT
    with tempfile.TemporaryDirectory(prefix='pte-reproduction-') as directory:
        root = Path(directory)
        scripts = root / 'scripts' / 'pte'
        scripts.mkdir(parents=True)
        for name in ('count_records.py', 'count_complete_native.py', 'count_complete_pte.py',
                     'count_pte_native.cpp', 'run_pte_experiments.py', 'analyse_pte_experiments.py'):
            shutil.copy2(Path(__file__).with_name(name), scripts / name)
        source = root / 'data' / 'processed'
        output = root / 'results' / 'generated' / 'pte_experiments'
        source.mkdir(parents=True)
        output.mkdir(parents=True)
        stem = 'instance_corridor_timewindow_small'
        data = {'nodes': ['O', 'X', 'D'], 'source_sha256': 'test-source-v1',
                'arcs': [(0, 0, 2, 5, 2), (1, 0, 1, 20, 1), (2, 1, 2, 20, 2)],
                'commodities': [('K0', 0, 2, 5, 2), ('K1', 0, 2, 5, 3), ('K2', 2, 2, 3, 3)],
                'costs': np.full((3, 3), 2.0)}
        cache = source / f'{stem}.input.pkl'
        cache.write_bytes(pickle.dumps(data))
        target = output / f'{stem}.counts.json'

        def run(script, *args, succeeds=True):
            result = subprocess.run([sys.executable, str(scripts / script), *args],
                                    cwd=root, capture_output=True, text=True)
            assert (result.returncode == 0) == succeeds, result.stdout + result.stderr
            return result

        # A partial legacy file must be rejected by analysis and repaired by the counter.
        target.write_text(json.dumps({'status': 'partial'}), encoding='utf-8')
        (output / f'{stem}.pte.final.json').write_text(
            json.dumps({'commodities': 3, 'source_sha256': data['source_sha256']}), encoding='utf-8')
        result = run('analyse_pte_experiments.py', succeeds=False)
        assert 'complete counts required' in result.stderr, result.stderr
        assert not (output / 'main_results.csv').exists()
        result = run('count_complete_native.py')
        assert 'Compiling C++17 graph counter' in result.stdout, result.stdout
        complete = read_complete_count(target, 3)
        assert complete is not None
        assert tuple(complete[key] for key in ('states', 'transport', 'sink')) == (7, 4, 4)

        for mutation in ('status', 'aggregate', 'missing', 'duplicate', 'missing_total', 'missing_time', 'malformed'):
            bad = copy.deepcopy(complete)
            if mutation == 'status':
                bad['status'] = 'partial'
            elif mutation == 'aggregate':
                bad['transport'] += 1
            elif mutation == 'missing':
                bad['records'].pop()
            elif mutation == 'duplicate':
                bad['records'][1]['k'] = 0
            elif mutation == 'missing_total':
                del bad['full_states']
            elif mutation == 'missing_time':
                del bad['count_seconds']
            else:
                bad['records'][0] = None
            assert not is_complete_count(bad, 3), mutation
        assert not is_complete_count([], 3)

        saved = target.read_bytes()
        assert 'SKIP complete verified counts' in run('count_complete_native.py').stdout
        assert target.read_bytes() == saved
        run('count_complete_pte.py', '--force', '--max-states', '1', succeeds=False)
        assert target.read_bytes() == saved, 'Partial run overwrote complete results'
        partial = output / f'{stem}.counts.partial.json'
        assert json.loads(partial.read_text())['status'] == 'partial'
        assert read_complete_count(partial, 3) is None

        # Both implementations must agree on complete counts.
        run('count_complete_pte.py', '--force')
        python_count = read_complete_count(target, 3)
        for key in ('states', 'transport', 'sink', 'full_states', 'full_transport',
                    'full_sink', 'bound_states', 'bound_transport', 'bound_sink'):
            assert python_count[key] == complete[key], key
        assert 'COUNT START' in run('count_complete_native.py', '--force').stdout
        data['source_sha256'] = 'test-source-v2'
        cache.write_bytes(pickle.dumps(data))
        assert 'COUNT START' in run('count_complete_native.py').stdout
        assert read_complete_count(target, 3)['source_sha256'] == 'test-source-v2'
    print('PASS: entrypoint paths, native compilation, complete counts, partial rejection, '
          'safe reuse, forced recomputation and input hashes')


if __name__ == '__main__':
    main()

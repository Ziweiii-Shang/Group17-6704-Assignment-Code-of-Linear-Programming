"""Paired timing on unchanged-demand subsets of the nine supplied networks."""
import argparse
import gc
import json
from pathlib import Path
import pickle
from types import SimpleNamespace

from run_pte_experiments import OUT, DEFAULT_INPUT, run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--pattern', default='*.input.pkl')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--force', action='store_true', help='Rerun all LP pairs even if result files exist')
    args = parser.parse_args()
    settings = SimpleNamespace(max_edges=5_000_000, max_states=2_500_000,
                               preprocess_limit=180, solve_limit=180)
    pairs = []
    for path in sorted(args.input.glob(args.pattern)):
        instance_name = path.name[:-len('.input.pkl')] if path.name.endswith('.input.pkl') else path.stem
        with path.open('rb') as f:
            data = pickle.load(f)
        candidates = [k for k, c in enumerate(data['commodities']) if c[1] != c[2]]
        indices = sorted(candidates, key=lambda k: (data['commodities'][k][4], k))[:20]
        for rep in range(args.repeats):
            # Alternate run order so one method does not always run first.
            methods = ['reachable_te', 'pte'] if rep % 2 == 0 else ['pte', 'reachable_te']
            results = {}
            for method in methods:
                suffix = f'.subset20.r{rep + 1}'
                output = OUT / f'{instance_name}.{method}{suffix}.json'
                if output.exists() and not args.force:
                    result = json.loads(output.read_text())
                    if result.get('source_sha256') != data['source_sha256'] or result.get('commodity_indices') != indices:
                        raise ValueError(f'{output.name}: saved benchmark does not match this input/subset; rerun with --force')
                else:
                    result = run(path, settings, cached=True, subset=indices, method=method, suffix=suffix)
                results[method] = result
                gc.collect()
            pair = {'instance': instance_name, 'replicate': rep + 1, 'indices': indices}
            if all(r.get('lp_status') == 'Optimal' for r in results.values()):
                te, pte = results['reachable_te'], results['pte']
                gap = abs(te['objective'] - pte['objective']) / max(1, abs(te['objective']))
                assert gap < 1e-7, pair
                core_te, core_pte = [r['total_seconds'] - r['input_seconds'] for r in [te, pte]]
                pair.update(status='both_optimal', objective_relative_difference=gap,
                            core_te_seconds=core_te, core_pte_seconds=core_pte,
                            core_speedup=core_te / core_pte,
                            te_variables=te['variables'], pte_variables=pte['variables'])
            else:
                pair['status'] = 'comparison_unavailable'
            pairs.append(pair)
            (OUT / 'paired_benchmarks.json').write_text(json.dumps(pairs, indent=2), encoding='utf-8')
    print('PAIRED BENCHMARKS COMPLETE', len(pairs), flush=True)


if __name__ == '__main__':
    main()

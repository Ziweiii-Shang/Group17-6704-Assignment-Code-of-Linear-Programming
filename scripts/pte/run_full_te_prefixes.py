"""Reproduce Table 3: dense TE on shortest-budget prefixes of Random-small.

Each prefix runs in a fresh child process. Memory limits stop the child without
misreporting the stop as infeasibility or an LP optimum. The original reported
measurements are retained separately in results/full_te_prefixes.csv.
"""
import argparse
import json
import multiprocessing as mp
from pathlib import Path
import pickle
import time
import traceback

import psutil
from run_pte_experiments import DEFAULT_INPUT, ROOT, dense_expand, optimize, peak_rss_bytes


def worker(cache, indices, solve_limit, log_path, pipe):
    try:
        started = time.perf_counter()
        data = pickle.loads(Path(cache).read_bytes())
        stats, graph = dense_expand(data, indices, 2**63 - 1, 2**63 - 1)
        result = optimize(data, indices, graph, solve_limit, Path(log_path))
        pipe.send({'status': result['lp_status'], **result,
                   'expansion_seconds': stats['expansion_seconds'],
                   'worker_seconds': time.perf_counter() - started,
                   'peak_rss_bytes': peak_rss_bytes()})
    except Exception:
        pipe.send({'status': 'error', 'error': traceback.format_exc()})
    finally:
        pipe.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT / 'instance_random_timewindow_small.input.pkl')
    parser.add_argument('--max-demands', type=int, default=5)
    parser.add_argument('--solve-limit', type=float, default=7200)
    parser.add_argument('--process-limit-gib', type=float, default=8)
    parser.add_argument('--free-reserve-gib', type=float, default=6)
    parser.add_argument('--output', type=Path, default=ROOT / 'results/generated/full_te_prefixes')
    args = parser.parse_args()
    if args.max_demands < 1 or min(args.solve_limit, args.process_limit_gib) <= 0 or args.free_reserve_gib < 0:
        parser.error('Demand count and limits must be positive; free reserve may be zero.')
    data = pickle.loads(args.input.read_bytes())
    eligible = sorted((k for k, c in enumerate(data['commodities']) if c[1] != c[2]),
                      key=lambda k: (data['commodities'][k][4], k))
    if args.max_demands > len(eligible):
        parser.error('Requested more nontrivial commodities than available.')
    args.output.mkdir(parents=True, exist_ok=True)
    context = mp.get_context('spawn')
    rows = []
    for count in range(1, args.max_demands + 1):
        indices = eligible[:count]
        states = sum(len(data['nodes']) * (data['commodities'][k][4] + 1) for k in indices)
        variables = sum(sum(max(0, data['commodities'][k][4] - a[4] + 1) for a in data['arcs'])
                        + data['commodities'][k][4] + 1 for k in indices)
        base = {'instance': args.input.name.removesuffix('.input.pkl'), 'demands': count,
                'commodity_indices': indices, 'variables': variables,
                'constraints': states + count + len(data['arcs']),
                'source_sha256': data['source_sha256'], 'solve_limit_seconds': args.solve_limit,
                'process_limit_gib': args.process_limit_gib, 'free_reserve_gib': args.free_reserve_gib}
        print(f'PREFIX {count}: indices={indices}, variables={variables:,}, rows={base["constraints"]:,}', flush=True)
        started = time.perf_counter()
        if psutil.virtual_memory().available < args.free_reserve_gib * 2**30:
            outcome = {'status': 'system_free_memory_guard', 'peak_rss_bytes': 0}
        else:
            receive, send = context.Pipe(duplex=False)
            process = context.Process(target=worker, args=(args.input, indices, args.solve_limit,
                                                         args.output / f'prefix_{count}.log', send))
            process.start()
            send.close()
            peak = 0
            outcome = None
            while process.is_alive():
                if receive.poll():
                    try:
                        outcome = receive.recv()
                    except EOFError:
                        pass
                    break
                try:
                    info = psutil.Process(process.pid).memory_info()
                    peak = max(peak, info.rss, getattr(info, 'peak_wset', 0))
                    reason = ('process_memory_guard' if info.rss > args.process_limit_gib * 2**30 else
                              'system_free_memory_guard' if psutil.virtual_memory().available < args.free_reserve_gib * 2**30 else None)
                    if reason:
                        process.terminate()
                        outcome = {'status': reason}
                        break
                except psutil.NoSuchProcess:
                    break
                time.sleep(0.1)
            process.join()
            if outcome is None and receive.poll():
                try:
                    outcome = receive.recv()
                except EOFError:
                    pass
            receive.close()
            if outcome is None:
                outcome = {'status': 'worker_failed', 'exit_code': process.exitcode}
            outcome['peak_rss_bytes'] = max(peak, outcome.get('peak_rss_bytes', 0))
        row = {**base, **outcome, 'elapsed_seconds': time.perf_counter() - started}
        rows.append(row)
        (args.output / 'full_te_prefixes.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
        print(f'PREFIX {count}: {row["status"]}, objective={row.get("objective")}, elapsed={row["elapsed_seconds"]:.2f}s', flush=True)
        if row['status'] in ('error', 'worker_failed'):
            raise SystemExit(row.get('error', str(row)))
        if row['status'] != 'Optimal':
            break


if __name__ == '__main__':
    main()

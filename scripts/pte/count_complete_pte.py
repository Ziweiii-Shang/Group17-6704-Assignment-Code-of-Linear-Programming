"""Count the exact retained graph one commodity at a time, without one global LP."""
from array import array
import argparse
import gc
import json
from pathlib import Path
import pickle
import time

from run_pte_experiments import OUT, DEFAULT_INPUT, bounds


def count_one(n, outgoing, commodity, remaining, max_states=5_000_000):
    _, o, d, _, budget = commodity
    queue = array('q', [o])
    visited = {o}
    cursor = 0
    edges = sinks = 0
    while cursor < len(queue):
        t, i = divmod(queue[cursor], n)
        sinks += i == d
        for _, j, tau in outgoing[i]:
            arrival = t + tau
            if arrival + remaining[j] > budget:
                continue
            edges += 1
            key = arrival * n + j
            if key not in visited:
                visited.add(key)
                queue.append(key)
        cursor += 1
        if len(visited) > max_states:
            return {'status': 'per_commodity_state_limit', 'states': len(visited), 'transport': edges, 'sink': sinks}
    return {'status': 'complete', 'states': len(visited), 'transport': edges, 'sink': sinks}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--pattern', default='*.input.pkl')
    args = parser.parse_args()
    for path in sorted(args.input.glob(args.pattern)):
        instance_name = path.name[:-len('.input.pkl')] if path.name.endswith('.input.pkl') else path.stem
        target = OUT / f'{instance_name}.counts.json'
        if target.exists():
            continue
        with path.open('rb') as f:
            data = pickle.load(f)
        started = time.perf_counter()
        outgoing, distances, totals, _, bound_seconds = bounds(data, range(len(data['commodities'])))
        rows = []
        for k, commodity in enumerate(data['commodities']):
            begin = time.perf_counter()
            record = count_one(len(data['nodes']), outgoing, commodity, distances[k][1])
            rows.append({'k': k, 'commodity': commodity[0], 'budget_ms': commodity[4],
                         'seconds': time.perf_counter() - begin, **record})
            if k % 50 == 0:
                print(instance_name, 'count', k, 'states', sum(r['states'] for r in rows), flush=True)
        result = {'instance': instance_name, 'status': 'complete' if all(r['status'] == 'complete' for r in rows) else 'partial',
                  'states': sum(r['states'] for r in rows), 'transport': sum(r['transport'] for r in rows),
                  'sink': sum(r['sink'] for r in rows), 'bound_seconds': bound_seconds,
                  'count_seconds': time.perf_counter() - started,
                  'input_included': False, 'lp_built': False, 'records': rows, **totals}
        target.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('COUNT RESULT', instance_name, result['status'], result['states'], result['transport'], result['count_seconds'], flush=True)
        gc.collect()


if __name__ == '__main__':
    main()

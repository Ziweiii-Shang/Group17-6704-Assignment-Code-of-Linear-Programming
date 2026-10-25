"""Exact size counting with a bitmap/queue kernel; no LP is built or solved."""
import argparse
import json
import os
import pickle
from pathlib import Path
import shlex
import subprocess
import time
from run_pte_experiments import OUT, DEFAULT_INPUT, bounds
from count_records import read_complete_count

def compile_counter():
    source = Path(__file__).with_name('count_pte_native.cpp')
    binary = source.with_name('count_pte_native.exe' if os.name == 'nt' else 'count_pte_native')
    if not binary.exists() or binary.stat().st_mtime < source.stat().st_mtime:
        compiler = shlex.split(os.environ.get('CXX', 'c++'))
        print('Compiling C++17 graph counter...', flush=True)
        try:
            subprocess.run(compiler + ['-O3', '-std=c++17', str(source), '-o', str(binary)], check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise SystemExit('A C++17 compiler is required. Install clang++ or g++, or set CXX to its command.') from exc
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--pattern', default='*.input.pkl')
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--force', action='store_true', help='Recompute existing complete counts')
    args = parser.parse_args()
    paths = sorted(args.input.glob(args.pattern))
    if not paths:
        parser.error('No input caches match the requested input/pattern')
    args.output.mkdir(parents=True, exist_ok=True)
    binary = None
    for path in paths:
        instance_name = path.name[:-len('.input.pkl')] if path.name.endswith('.input.pkl') else path.stem
        target = args.output / f'{instance_name}.counts.json'
        with path.open('rb') as f:
            data = pickle.load(f)
        previous = read_complete_count(target, len(data['commodities']))
        if not args.force and previous and previous.get('source_sha256') == data['source_sha256']:
            print('SKIP complete verified counts', instance_name, flush=True)
            continue
        if binary is None:
            binary = compile_counter()
        print('COUNT START', instance_name, flush=True)
        started = time.perf_counter()
        _, distances, totals, _, bound_seconds = bounds(data, range(len(data['commodities'])))
        lines = [f'{len(data["nodes"])} {len(data["arcs"])} {len(data["commodities"])}']
        lines += [f'{i} {j} {t}' for _, i, j, _, t in data['arcs']]
        for k, (_, o, d, q, budget) in enumerate(data['commodities']):
            lines.append(f'{o} {d} {budget}')
            lines.append(' '.join(map(str, distances[k][1])))
        process = subprocess.run([str(binary)], input='\n'.join(lines)+'\n',
                                 stdout=subprocess.PIPE, text=True, check=True)
        records = []
        for line in process.stdout.splitlines():
            k, states, edges, sinks, seconds = line.split()
            k = int(k)
            records.append({'k': k, 'commodity': data['commodities'][k][0], 'states': int(states),
                            'transport': int(edges), 'sink': int(sinks), 'seconds': float(seconds), 'status': 'complete'})
        if [r['k'] for r in records] != list(range(len(data['commodities']))):
            raise RuntimeError(f'{instance_name}: native counter returned incomplete commodity records')
        result = {'instance': instance_name, 'status': 'complete', 'source_sha256': data['source_sha256'],
                  'count_implementation': 'C++ bitmap/queue',
                  'states': sum(r['states'] for r in records), 'transport': sum(r['transport'] for r in records),
                  'sink': sum(r['sink'] for r in records), 'bound_seconds': bound_seconds,
                  'count_seconds': time.perf_counter()-started, 'input_included': False, 'lp_built': False,
                  'records': records, **totals}
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(result, indent=2), encoding='utf-8')
        temporary.replace(target)
        print('COUNT RESULT', instance_name, result['states'], result['transport'], result['count_seconds'], flush=True)


if __name__ == '__main__':
    main()

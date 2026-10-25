"""Exact size counting with a bitmap/queue kernel; no LP is built or solved."""
import argparse
import json
import pickle
from pathlib import Path
import subprocess
import time
from run_pte_experiments import OUT, DEFAULT_INPUT, bounds

parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
parser.add_argument('--pattern', default='*.input.pkl')
args = parser.parse_args()
binary = Path(__file__).parent / 'count_pte_native'
for path in sorted(args.input.glob(args.pattern)):
    instance_name = path.name[:-len('.input.pkl')] if path.name.endswith('.input.pkl') else path.stem
    target = OUT / f'{instance_name}.counts.json'
    if target.exists():
        continue
    with path.open('rb') as f:
        data = pickle.load(f)
    started = time.perf_counter()
    outgoing, distances, totals, _, bound_seconds = bounds(data, range(len(data['commodities'])))
    lines = [f'{len(data["nodes"])} {len(data["arcs"])} {len(data["commodities"])}']
    lines += [f'{i} {j} {t}' for _,i,j,_,t in data['arcs']]
    for k, (_,o,d,q,budget) in enumerate(data['commodities']):
        lines.append(f'{o} {d} {budget}')
        lines.append(' '.join(map(str, distances[k][1])))
    process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    # Payloads are below a megabyte, so communicate drains stdout while writing stdin.
    stdout, _ = process.communicate('\n'.join(lines)+'\n')
    assert process.returncode == 0
    records=[]
    for line in stdout.splitlines():
        k,states,edges,sinks,seconds=line.split(); k=int(k)
        records.append({'k':k, 'commodity':data['commodities'][k][0], 'states':int(states),
                        'transport':int(edges), 'sink':int(sinks), 'seconds':float(seconds), 'status':'complete'})
    assert len(records)==len(data['commodities'])
    result={'instance':instance_name,'status':'complete', 'count_implementation':'C++ bitmap/queue',
            'states':sum(r['states'] for r in records),'transport':sum(r['transport'] for r in records),
            'sink':sum(r['sink'] for r in records),'bound_seconds':bound_seconds,
            'count_seconds':time.perf_counter()-started, 'input_included':False,'lp_built':False,
            'records':records,**totals}
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('COUNT RESULT',instance_name,result['states'],result['transport'],result['count_seconds'],flush=True)

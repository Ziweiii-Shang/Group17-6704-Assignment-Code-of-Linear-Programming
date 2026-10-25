import gc
import argparse
import json
from pathlib import Path
import pickle
from types import SimpleNamespace
from run_pte_experiments import DEFAULT_INPUT, OUT, run

args=SimpleNamespace(max_edges=8_000_000,max_states=3_000_000,preprocess_limit=180,solve_limit=180)
parser=argparse.ArgumentParser(description='Compare one full-lattice TE and PTE solve per instance.')
parser.add_argument('--force',action='store_true',help='Ignore saved validation records and solve again')
options=parser.parse_args()
results=[]
for path in sorted(Path(DEFAULT_INPUT).glob('*.input.pkl')):
    instance_name = path.name[:-len('.input.pkl')]
    with path.open('rb') as f:
        data=pickle.load(f)
    eligible=[k for k,c in enumerate(data['commodities']) if c[1]!=c[2]]
    k=min(eligible,key=lambda k:(data['commodities'][k][4],k))
    pair={}
    for method in ['dense_te','pte']:
        target=OUT/f'{instance_name}.{method}.densecheck.json'
        if target.exists() and not options.force:
            result=json.loads(target.read_text())
            if result.get('source_sha256') != data['source_sha256']:
                raise ValueError(f'{instance_name}: saved {method} record belongs to a different source workbook; rerun with --force')
        else:
            result=run(path,args,cached=True,subset=[k],method=method,suffix='.densecheck')
        pair[method]=result
        gc.collect()
    te,pruned=pair['dense_te'],pair['pte']
    assert te['lp_status']==pruned['lp_status']=='Optimal'
    gap=abs(te['objective']-pruned['objective'])/max(1,abs(te['objective']))
    assert gap<1e-7
    results.append({'instance':instance_name,'k':k,'objective_relative_difference':gap,
                    'dense_variables':te['variables'],'pte_variables':pruned['variables'],
                    'dense_core_seconds':te['total_seconds']-te['input_seconds'],
                    'pte_core_seconds':pruned['total_seconds']-pruned['input_seconds']})
    (OUT/'dense_validation.json').write_text(json.dumps(results,indent=2))
print('FULL LATTICE VALIDATION COMPLETE',len(results),flush=True)

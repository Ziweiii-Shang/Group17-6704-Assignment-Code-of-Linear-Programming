"""Derive tables and figures solely from saved experiment records."""
import csv
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results'/'generated'/'pte_experiments'
OUT.mkdir(parents=True, exist_ok=True)
import os
os.environ.setdefault('MPLCONFIGDIR', str(OUT/'matplotlib-config'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

FIG=OUT/'figures'
FIG.mkdir(exist_ok=True)
families=['corridor','hub','random']
sizes=['small','middle','Large']
rows=[]
for family in families:
    for size in sizes:
        stem=f'instance_{family}_timewindow_{size}'
        c=json.loads((OUT/f'{stem}.counts.json').read_text())
        mainpath=OUT/f'{stem}.pte.final.json'
        if family=='random' and size=='Large':
            mainpath=OUT/f'{stem}.pte.final600.json'
        if not mainpath.exists():
            raise RuntimeError('Final main measurements are not complete')
        main=json.loads(mainpath.read_text())
        if main['status']=='complete':
            assert (c['states'],c['transport'],c['sink'])==(main['states'],main['transport'],main['sink'])
        full=c['full_transport']+c['full_sink']
        bound=c['bound_transport']+c['bound_sink']
        final=c['transport']+c['sink']
        row={'instance':stem,'measurement_record':mainpath.name,'family':family,'size':size,'nodes':main['nodes'],'arcs':main['arcs'],
             'commodities':main['commodities'],'full_states':c['full_states'],'full_variables':full,
             'bound_states':c['bound_states'],'bound_variables':bound,'pte_states':c['states'],
             'pte_transport':c['transport'],'pte_sink':c['sink'],'pte_variables':final,
             'pte_constraints':c['states']+main['commodities']+main['arcs'],
             'bound_reduction_pct':100*(1-bound/full),'reachability_reduction_pct':100*(1-final/bound),
             'total_reduction_pct':100*(1-final/full),'variable_compression':full/final,
             'decimal_orders_removed':np.log10(full/final),
             'native_count_seconds':c['count_seconds'],'main_status':main.get('lp_status',main['status']),
             'input_seconds':main['input_seconds'],'bounds_seconds':main['bounds_seconds'],
             'expansion_seconds':main['expansion_seconds'],'backward_seconds':main.get('backward_seconds'),
             'preprocess_seconds':main['preprocess_seconds'],'build_seconds':main.get('build_seconds'),
             'solve_seconds':main.get('solve_seconds'),'total_seconds':main['total_seconds'],
             'peak_rss_gib':main['peak_process_rss_bytes']/2**30,'objective':main.get('objective'),
             'max_flow_balance_residual':main.get('max_flow_balance_residual'),
             'max_demand_residual':main.get('max_demand_residual'),
             'max_capacity_violation':main.get('max_capacity_violation'),
             'duality_gap_absolute':main.get('duality_gap_absolute'),
             'same_od_commodities':main['same_od_commodities']}
        rows.append(row)

with (OUT/'main_results.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
paired=json.loads((OUT/'paired_benchmarks.json').read_text())
bench=[]
for row in rows:
    reps=[p for p in paired if p['instance']==row['instance']]
    assert len(reps)==3 and all(p['status']=='both_optimal' for p in reps)
    te=statistics.median(p['core_te_seconds'] for p in reps)
    pte=statistics.median(p['core_pte_seconds'] for p in reps)
    bench.append({'instance':row['instance'],'te_variables':reps[0]['te_variables'],
                  'pte_variables':reps[0]['pte_variables'],'median_te_core_seconds':te,
                  'median_pte_core_seconds':pte,'ratio_of_median_times':te/pte,
                  'pte_min_seconds':min(p['core_pte_seconds'] for p in reps),
                  'pte_max_seconds':max(p['core_pte_seconds'] for p in reps),
                  'max_objective_relative_difference':max(p['objective_relative_difference'] for p in reps)})
with (OUT/'paired_summary.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.DictWriter(f,fieldnames=list(bench[0]));writer.writeheader();writer.writerows(bench)
summary={'main':rows,'paired':bench,'dense_validation':json.loads((OUT/'dense_validation.json').read_text())}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
labels=[f'{r["family"].title()}\n{r["size"].title()}' for r in rows]
x=np.arange(9)
fig,ax=plt.subplots(figsize=(11,4.8))
for shift,key,color,label in [(-.25,'full_variables','#555555','Full time grid (counted)'),
                             (0,'bound_variables','#a57826','After shortest-time bounds (counted)'),
                             (.25,'pte_variables','#257d78','After exact reachability (counted)')]:
    ax.bar(x+shift,[r[key] for r in rows],width=.24,color=color,label=label)
ax.set_yscale('log');ax.set_ylabel('Number of LP variables (log scale)')
ax.set_xticks(x,labels)
ax.legend(fontsize=9,loc='lower left',bbox_to_anchor=(0,1.01),frameon=False)
ax.grid(axis='y',alpha=.2)
fig.tight_layout();fig.savefig(FIG/'model_size.png',dpi=180);plt.close(fig)

random=[r for r in rows if r['family']=='random']
fig,ax=plt.subplots(figsize=(8,4.5));bottom=np.zeros(3)
for key,label,color in [('input_seconds','Excel input','#555555'),('preprocess_seconds','Pruning','#257d78'),
                        ('build_seconds','LP construction','#a57826'),('solve_seconds','HiGHS solve','#825373')]:
    vals=np.array([r[key] for r in random]);ax.bar(range(3),vals,bottom=bottom,label=label,color=color);bottom+=vals
ax.set_xticks(range(3),[r['size'].title() for r in random]);ax.set_ylabel('Elapsed time (seconds)')
ax.set_title('Complete Random instances');ax.legend();ax.grid(axis='y',alpha=.2)
fig.tight_layout();fig.savefig(FIG/'runtime_breakdown.png',dpi=180);plt.close(fig)

fig,ax=plt.subplots(figsize=(10,4.5))
ax.bar(x,[r['ratio_of_median_times'] for r in bench],color='#257d78')
ax.set_yscale('log');ax.axhline(1,color='#555555',linewidth=1)
ax.set_xticks(x,labels);ax.set_ylabel('Ratio of median core times')
ax.set_title('20-demand subsets: source-reachable TE-LP / PTE-LP (3 repeats)')
ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(FIG/'paired_speedup.png',dpi=180);plt.close(fig)
print(json.dumps(summary,indent=2))

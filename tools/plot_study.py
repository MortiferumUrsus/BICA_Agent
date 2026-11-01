"""Render saved offline results; never makes API requests."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def plot(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["summaries"]
    profiles = ["4.1-mini", "5.4-nano-none", "5.4-nano-low", "5.4-mini-low"]
    methods = ["summary", "reflexive", "last_window", "full_context"]
    colors = {"summary":"#3477a9", "reflexive":"#c36a2d", "last_window":"#949494", "full_context":"#31876b"}
    labels = {"personamem":"PersonaMem · 16 personas", "babilong":"BABILong · 20 examples", "goal_shift":"Custom goal shifts · 12 scenarios"}
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False,"svg.fonttype":"none"})
    fig, axes = plt.subplots(1,3,figsize=(15,5),layout="constrained")
    for ax,dataset in zip(axes,labels):
        active = methods if dataset == "personamem" else methods[:2]
        width=.8/len(active)
        for j,method in enumerate(active):
            subset=[next(r for r in rows if r['dataset']==dataset and r['profile']==p and r['mode']==method) for p in profiles]
            values=np.array([r['accuracy'] for r in subset])*100
            ci=np.array([r['wilson_95_ci'] for r in subset])*100
            positions=np.arange(4)-.4+(j+.5)*width
            ax.bar(positions,values,width,label=method,color=colors[method])
            ax.errorbar(positions,values,yerr=np.maximum(0,np.stack([values-ci[:,0],ci[:,1]-values])),fmt='none',ecolor='#333333',capsize=2,linewidth=.7)
        ax.set(title=labels[dataset],xticks=np.arange(4),xticklabels=profiles,ylim=(0,105),ylabel="Correct answers (%)")
        ax.tick_params(axis='x',rotation=25)
        ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    handles,legend=axes[0].get_legend_handles_labels()
    fig.legend(handles,legend,loc='outside lower center',ncol=4,frameon=False)
    fig.suptitle("Memory methods: accuracy and 95% Wilson intervals\nFull context uses a larger context budget; one run per condition",fontsize=13)
    for ext in ('png','svg','pdf'):
        fig.savefig(path.parent/f'accuracy.{ext}',dpi=170)
    plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
    for ax,dataset in zip(axes,labels):
        active=methods if dataset=='personamem' else methods[:2]
        width=.8/len(active)
        for j,method in enumerate(active):
            subset=[next(r for r in rows if r['dataset']==dataset and r['profile']==p and r['mode']==method) for p in profiles]
            ax.bar(np.arange(4)-.4+(j+.5)*width,[r['cost_usd']/r['n'] for r in subset],width,label=method,color=colors[method])
        ax.set(title=labels[dataset],xticks=np.arange(4),xticklabels=profiles,ylabel='Mean API cost per example (USD)')
        ax.tick_params(axis='x',rotation=25);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    handles,legend=axes[0].get_legend_handles_labels()
    fig.legend(handles,legend,loc='outside lower center',ncol=4,frameon=False)
    fig.suptitle('Measured API cost, including retries and reasoning',fontsize=13)
    for ext in ('png','svg','pdf'):
        fig.savefig(path.parent/f'cost.{ext}',dpi=170)
    plt.close(fig)
    for name in ('accuracy.svg', 'cost.svg'):
        target = path.parent/name
        target.write_text('\n'.join(line.rstrip() for line in target.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results',type=Path)
    plot(parser.parse_args().results)

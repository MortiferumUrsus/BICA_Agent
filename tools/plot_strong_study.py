"""Plot the frozen follow-up scores without inference."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def plot(path):
    data=json.loads(path.read_text(encoding='utf-8'))
    rows=data['combined_summaries']
    titles={'personamem':'PersonaMem','babilong':'BABILong','goal_shift':'Custom goal shifts'}
    profiles={'5.4-mini-low':'GPT-5.4 mini','6.1-sol-low':'GPT-6.1 Sol','6-astra-low':'GPT-6 Astra'}
    colors=['#3477a9','#c36a2d']
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
    for metric in ['accuracy','cost']:
        fig,axes=plt.subplots(1,3,figsize=(14,5.5))
        fig.subplots_adjust(left=.06,right=.99,bottom=.23,top=.77,wspace=.28)
        for ax,dataset in zip(axes,titles):
            active=[p for p in profiles if any(r['profile']==p and r['dataset']==dataset and r['mode']=='summary' for r in rows)]
            for index,mode in enumerate(['summary','reflexive']):
                values=[next(r for r in rows if r['profile']==p and r['dataset']==dataset and r['mode']==mode) for p in active]
                y=np.array([r['accuracy']*100 if metric=='accuracy' else r['cost_usd']/r['n'] for r in values])
                x=np.arange(len(active))+(index-.5)*.34
                bars=ax.bar(x,y,.34,label=mode,color=colors[index])
                if metric=='accuracy':
                    ci=np.array([r['wilson_95_ci'] for r in values])*100
                    ax.errorbar(x,y,yerr=np.maximum(0,np.stack([y-ci[:,0],ci[:,1]-y])),fmt='none',ecolor='#333333',capsize=3,linewidth=.8)
                    ax.set_ylim(0,110)
                else:
                    ax.margins(y=.15)
                for b,r in zip(bars,values):
                    label=f"{r['correct']}/{r['n']}" if metric=='accuracy' else f"${r['cost_usd']/r['n']:.3f}"
                    ax.text(b.get_x()+b.get_width()/2,b.get_height(),label,ha='center',va='bottom',fontsize=9)
            ax.set_title(titles[dataset]);ax.set_xticks(np.arange(len(active)),[profiles[p] for p in active],rotation=15)
            ax.set_ylabel('Correct answers (%)' if metric=='accuracy' else 'Mean API cost per example (USD)')
            ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        handles,labels=axes[0].get_legend_handles_labels()
        fig.legend(handles,labels,loc='lower center',ncol=2,frameon=False)
        fig.suptitle(('Stronger models: accuracy with 95% Wilson intervals' if metric=='accuracy' else 'Stronger models: measured API cost')+'\nReasoning low; Astra uses a budget-limited subset (see matched-ID comparisons)',fontsize=13,y=.97)
        for ext in ['png','svg','pdf']:fig.savefig(path.parent/f'{metric}.{ext}',dpi=170)
        plt.close(fig)
        svg=path.parent/f'{metric}.svg'
        svg.write_text('\n'.join(s.rstrip() for s in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('results',type=Path);plot(parser.parse_args().results)

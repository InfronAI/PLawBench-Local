"""Export standard matplotlib figures from real experiment summaries."""
import argparse
import json
from pathlib import Path


def plot(root, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data=json.loads((root/'summary.json').read_text())
    candidate=json.loads((root/'generation_manifest.json').read_text())['model']['model'].split('/')[-1]
    if data['coverage']['graded'] == 0:
        raise ValueError('No actual grades to plot')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig, axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    for ax,key,title in zip(axes,['tasks','case_dimensions'],['Public task scores · 95% bootstrap CI','Case analysis dimensions']):
        rows=data[key]
        names=list(rows)
        vals=[rows[n]['score_percent'] for n in names]
        y=range(len(names))
        ax.barh(y,vals,color=['#107d7a','#247aa6','#6966b5','#b47730'][:len(names)],height=.58)
        ax.set_yticks(list(y),[n.replace('_',' ').capitalize() for n in names])
        ax.invert_yaxis();ax.set_xlim(0,100);ax.set_xlabel('Earned / available rubric points (%)');ax.set_title(title,pad=16)
        ax.xaxis.grid(True,alpha=.15);ax.set_axisbelow(True)
        for i,v in enumerate(vals):
            ax.text(v-1.5 if v>90 else v+1.5,i-.2,f'{v:.2f}',va='center',
                    ha='right' if v>90 else 'left',color='white' if v>90 else '#182331',fontsize=10)
        if key=='tasks':
            for i,n in enumerate(names):
                interval=rows[n]['bootstrap_95ci']
                if interval:
                    ax.plot(interval,[i,i],color='#182331',lw=1.5)
    fig.suptitle('PLawBench · M1 local public-data experiment',fontweight='bold',fontsize=15)
    fig.supxlabel(f"{data['coverage']['graded']}/{data['coverage']['selected']} graded · {candidate} · uncalibrated local judge",fontsize=9)
    output.mkdir(parents=True,exist_ok=True)
    for suffix in ['png','svg']:
        fig.savefig(output/f'results.{suffix}',dpi=170,facecolor='white')
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,default=Path('experiments/m1-public'))
    p.add_argument('--output',type=Path,default=Path('docs/assets'))
    a=p.parse_args();plot(a.run,a.output)

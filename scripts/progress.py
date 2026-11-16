"""Read live checkpoint progress without loading a model or taking the writer lock."""
import argparse
import json
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('run',type=Path,nargs='?',default=Path('experiments/m1-public'))
args=parser.parse_args()
root=args.run
samples=json.loads((root/'samples.json').read_text()) if (root/'samples.json').exists() else []
predictions=[json.loads(p.read_text()) for p in (root/'predictions').glob('*.json')]
grades=[json.loads(p.read_text()) for p in (root/'grades').glob('*.json')]
attempts=[a for g in grades for a in g.get('attempts',[])]
print(json.dumps({'selected':len(samples),'generated':len(predictions),
                  'graded':sum(g['status']=='ok' for g in grades),'judge_failed':sum(g['status']!='ok' for g in grades),
                  'generation_tokens':sum(p['generation_tokens'] for p in predictions),
                  'truncated':sum(p['finish_reason']=='length' for p in predictions),
                  'generation_minutes':round(sum(p['elapsed_seconds'] for p in predictions)/60,2),
                  'judge_tokens':sum(a['generation_tokens'] for a in attempts),
                  'judge_minutes':round(sum(a['elapsed_seconds'] for a in attempts)/60,2),
                  'judge_retries':sum(max(0,len(g.get('attempts',[]))-1) for g in grades),
                  'peak_memory_gb':round(max((p['peak_memory_gb'] for p in predictions+attempts),default=0),2)},indent=2))

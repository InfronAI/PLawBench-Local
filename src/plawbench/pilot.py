"""Prepare blank human-rating forms; never substitute synthetic human judgments."""
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import random
from .io import write_json, digest


def export_pilot(run, output, seed=42):
    run, output = Path(run), Path(output)
    samples = json.loads((run/'samples.json').read_text())
    by_domain = defaultdict(list)
    for s in samples:
        if s['task'] == 'case_analysis':
            by_domain[s['domain']].append(s)
    rng = random.Random(seed)
    selected = []
    for domain in sorted(by_domain):
        rows = by_domain[domain]
        selected.extend(rng.sample(rows, max(1,math.ceil(len(rows)*.1))))
    for task, requested in [('consultation',20),('plaintiff',10),('defendant',10)]:
        rows = [s for s in samples if s['task']==task]
        selected.extend(rng.sample(rows,min(requested,len(rows))))
    selected.sort(key=lambda s:s['id'])
    records = []
    for s in selected:
        path = run/'predictions'/f"{s['id']}.json"
        if not path.exists():
            raise ValueError(f"Pilot needs generated answers; missing {s['id']}")
        p=json.loads(path.read_text())
        if digest(p['text']) != p['response_sha256']:
            raise ValueError(f"Prediction integrity mismatch: {s['id']}")
        records.append({'id':s['id'],'task':s['task'],'domain':s['domain'],
                        'generation_instructions':s['messages'][0]['content'],
                        'question':s['messages'][-1]['content'],'response':p['text'],
                        'rubrics':s['rubrics'],'max_points':s['max_points'],
                        'human_rating_1':'','human_rating_2':'','human_rating_3':''})
    output.mkdir(parents=True,exist_ok=True)
    write_json(output/'annotation_materials.json', records)
    with (output/'ratings.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['id','task','domain','human_rating_1','human_rating_2','human_rating_3'])
        writer.writeheader()
        for r in records:writer.writerow({k:r[k] for k in writer.fieldnames})
    manifest={'seed':seed,'count':len(records),'selection':'ceil(10%) per released case domain; up to 20 consultation and 10 per drafting subtype',
              'limitation':'Single local candidate only; public consultation/drafting counts are below the paper pilot targets. Ratings intentionally blank.',
              'source_run':str(run),'sample_ids':[r['id'] for r in records]}
    write_json(output/'pilot_manifest.json',manifest)
    return manifest

"""Preserve verified work when repairing the released consultation's duplicate IDs.

This deliberately handles only the observed consultation-012 normalization fix.
The source run is retained intact; the receipt identifies every reused record.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path

from plawbench.data import load_dataset
from plawbench.io import digest, file_hash, write_json
from plawbench.pipeline import run_lock, stage_manifest, export_records, now
from plawbench.scoring import judge_messages, parse_scores


def migrate(source, destination):
    source, destination = source.resolve(), destination.resolve()
    if destination.exists():
        raise ValueError('Destination must not exist; never overwrite a run')
    with run_lock(source):
        old = json.loads((source/'samples.json').read_text())
        samples, dataset = load_dataset()
        assert len(old) == len(samples) == 280
        changed = []
        for before, after in zip(old, samples):
            expected = deepcopy(before)
            if before['task'] == 'consultation':
                for i,rubric in enumerate(expected['rubrics'],1):
                    rubric['id'] = f'q{i}'
            assert expected == after, f"Unexpected dataset change: {before['id']}"
            if before != after:
                changed.append(before['id'])
        assert changed == ['consultation-012']
        manifests = {stage:json.loads((source/f'{stage}_manifest.json').read_text())
                     for stage in ['generation','judge']}
        assert all(m['samples_sha256'] == digest(old) for m in manifests.values())
        predictions, grades = [], []
        for before in old:
            sid = before['id']
            p = json.loads((source/'predictions'/f'{sid}.json').read_text())
            g = json.loads((source/'grades'/f'{sid}.json').read_text())
            assert p['input_sha256'] == digest(before['messages'])
            assert p['response_sha256'] == digest(p['text']) == g['response_sha256']
            assert p['fingerprint'] == manifests['generation']['fingerprint']
            assert g['fingerprint'] == manifests['judge']['fingerprint']
            if sid in changed:
                assert g['status'] == 'failed', 'Changed rubric must be judged anew'
            else:
                assert g['status'] == 'ok'
                assert parse_scores(g['attempts'][-1]['text'],before['rubrics']) == g['scores']
            predictions.append(p); grades.append(g)
        destination.mkdir()
        write_json(destination/'samples.json',samples)
        write_json(destination/'dataset_manifest.json',dataset)
        generation = stage_manifest(destination,'generation',manifests['generation']['config'],samples,manifests['generation']['model'])
        judge_config = deepcopy(manifests['judge']['config'])
        judge_config['inputs_sha256'] = digest([judge_messages(s,p['text']) for s,p in zip(samples,predictions)])
        judge = stage_manifest(destination,'judge',judge_config,samples,manifests['judge']['model'])
        records = []
        for before,after,p,g in zip(old,samples,predictions,grades):
            sid = after['id']
            for folder,record,manifest in [('predictions',p,generation),('grades',g,judge)]:
                original = source/folder/f'{sid}.json'
                provenance = {'record':os.path.relpath(original,destination),
                              'record_sha256':file_hash(original),
                              'original_fingerprint':record['fingerprint'],
                              'stage_input_unchanged':folder == 'predictions' or sid not in changed}
                record['fingerprint'] = manifest['fingerprint']
                if folder == 'grades' and sid in changed:
                    record['inherited_attempts'] = {**provenance,'count':len(record['attempts']),
                        'reason':'These failed attempts used duplicate rubric IDs; retained for timing and failure evidence only'}
                else:
                    record['reused_from'] = provenance
                if folder == 'grades' and sid not in changed:
                    assert judge_messages(before,p['text']) == judge_messages(after,p['text'])
                write_json(destination/folder/f'{sid}.json',record)
                records.append({'id':sid,'folder':folder,**provenance})
        for name in ['judge_manual_audit.json','judge_evidence_audit.json']:
            path = source/name
            if path.exists():
                audit = json.loads(path.read_text())
                audit['evidence_run'] = os.path.relpath(source,destination)
                write_json(destination/name,audit)
        receipt = {'created_at':now(),'source_run':os.path.relpath(source,destination),
                   'reason':'Repair duplicate source numbering without changing rubric text, allocations or generation inputs',
                   'changed_samples':changed,'reused_predictions':280,'reused_valid_grades':279,
                   'pending_rejudgment':changed,'source_manifests':{k:file_hash(source/f'{k}_manifest.json') for k in manifests},
                   'records':records}
        write_json(destination/'normalization_migration.json',receipt)
        for folder in ['predictions','grades']:
            export_records(destination,folder,samples)
        (destination/'README.md').write_text('# Complete public reproduction\n\n'
            'All generation inputs and 279 valid judge inputs are identical to the preserved '
            '[pre-correction run](../m1-public-before-rubric-id-fix/README.md). '
            'Their real outputs are reused with per-record provenance. Only consultation-012 '
            'is judged again after assigning distinct IDs to three separately scored source entries '
            'all numbered 10. Original text and all 33 points are retained. '
            'See `normalization_migration.json`; earlier failed attempts remain explicitly labeled.\n')
        print(json.dumps({k:v for k,v in receipt.items() if k != 'records'},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args = parser.parse_args()
    migrate(args.source,args.destination)

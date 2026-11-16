"""Verify completed run artifacts against source rubrics and content hashes."""
import argparse
import json
from pathlib import Path
from plawbench.io import digest, file_hash
from plawbench.scoring import parse_scores, judge_messages
from plawbench.analysis import summarize


def verify(root):
    samples=json.loads((root/'samples.json').read_text())
    manifests={name:json.loads((root/f'{name}_manifest.json').read_text()) for name in ['generation','judge']}
    for manifest in manifests.values():
        assert digest(samples)==manifest['samples_sha256'], 'Sample selection hash mismatch'
        assert digest({k:manifest[k] for k in ['config','samples_sha256','model']})==manifest['fingerprint'], 'Manifest identity mismatch'
    dataset_manifest=json.loads((root/'dataset_manifest.json').read_text())
    source_root=Path(__file__).resolve().parents[1]
    for name,expected_hash in dataset_manifest['sources'].items():
        assert file_hash(source_root/name)==expected_hash, f'Source data changed: {name}'
    preds,grades=[],[]
    reused_count=0
    inherited_count=0
    def verify_provenance(record, sample, folder):
        provenance=record.get('reused_from') or record.get('inherited_attempts')
        if not provenance:
            return
        path=root/provenance['record']
        assert file_hash(path)==provenance['record_sha256'], 'Reused source record changed'
        original=json.loads(path.read_text())
        assert original['fingerprint']==provenance['original_fingerprint']
        assert original['response_sha256']==record['response_sha256']
        if 'reused_from' in record:
            assert provenance['stage_input_unchanged'] is True
            before={k:v for k,v in original.items() if k!='fingerprint'}
            after={k:v for k,v in record.items() if k not in ['fingerprint','reused_from']}
            assert before==after, 'Reused output payload changed'
            old_samples=json.loads((path.parent.parent/'samples.json').read_text())
            old_sample=next(s for s in old_samples if s['id']==sample['id'])
            if folder=='predictions':
                assert old_sample['messages']==sample['messages']
            else:
                text=json.loads((root/'predictions'/path.name).read_text())['text']
                assert judge_messages(old_sample,text)==judge_messages(sample,text)
        else:
            assert provenance['stage_input_unchanged'] is False
            assert original['status']=='failed'
            assert record['attempts'][:provenance['count']]==original['attempts']
    for sample in samples:
        p=json.loads((root/'predictions'/f"{sample['id']}.json").read_text())
        g=json.loads((root/'grades'/f"{sample['id']}.json").read_text())
        verify_provenance(p,sample,'predictions')
        verify_provenance(g,sample,'grades')
        reused_count+=int('reused_from' in p)+int('reused_from' in g)
        inherited_count+=g.get('inherited_attempts',{}).get('count',0)
        assert p['id']==g['id']==sample['id']
        assert p['input_sha256']==digest(sample['messages'])
        assert p['response_sha256']==digest(p['text'])==g['response_sha256']
        assert p['fingerprint']==manifests['generation']['fingerprint']
        assert g['fingerprint']==manifests['judge']['fingerprint']
        assert g['status']=='ok', f"Incomplete grade: {g['id']}"
        assert parse_scores(g['attempts'][-1]['text'],sample['rubrics'])==g['scores']
        assert g['points']==sum(s['points'] for s in g['scores'])
        assert g['max_points']==sample['max_points']
        preds.append(p);grades.append(g)
    judge_prompt_verified=False
    if manifests['judge']['config']['protocol']=='rubric-json-v2-full-instructions':
        actual_inputs=digest([judge_messages(s,p['text']) for s,p in zip(samples,preds)])
        assert actual_inputs==manifests['judge']['config']['inputs_sha256'], 'Judge context hash mismatch'
        judge_prompt_verified=True
    expected=summarize(samples,preds,grades)
    actual=json.loads((root/'summary.json').read_text())
    # Both computations use the recorded sample order and deterministic bootstrap.
    for key,value in expected.items():
        assert value==actual.get(key), f'Analysis summary mismatch: {key}'
    files={str(p.relative_to(root)):file_hash(p) for p in sorted(root.rglob('*'))
           if p.is_file() and p.name not in ['artifact_checksums.json','verification.json','.running','run.log']}
    receipt={'sample_count':len(samples),'valid_grades':len(grades),'score_schema_and_source_maxima_revalidated':True,
             'dataset_source_hashes_verified':True,'manifest_identities_verified':True,
             'content_hashes_verified':True,'overall_recomputed':True,
             'all_summary_fields_recomputed':True,'judge_prompt_hash_verified':judge_prompt_verified,
             'reused_records_revalidated':reused_count,'inherited_failed_attempts_revalidated':inherited_count,
             'judge_prompt_check_scope':('Full original-instruction context reconstructed and hashed' if judge_prompt_verified
                                         else 'Legacy judge protocol; prompt hash not rederived by this v2 verifier')}
    (root/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (root/'artifact_checksums.json').write_text(json.dumps(files,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path)
    verify(p.parse_args().run)

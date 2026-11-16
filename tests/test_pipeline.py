from pathlib import Path
import json
import pytest
from plawbench.data import load_dataset, select
from plawbench.io import write_json
from plawbench.pipeline import generate, judge
from plawbench.analysis import summarize, ratio, pearson, ranks, calibrate

ROOT = Path(__file__).resolve().parents[1]


class FakeBackend:
    info = {'backend': 'test-only'}
    calls = 0
    mode = 'generate'

    def generate_batch(self, messages, budgets, temperature=0., seed=42):
        return [self.generate(m,b,temperature,seed) for m,b in zip(messages,budgets)]

    def generate(self, messages, max_tokens, temperature=0., seed=42):
        self.calls += 1
        if self.mode == 'judge':
            rubrics = json.loads(messages[1]['content'])['rubrics']
            text = json.dumps({'scores':[{'id':r['id'], 'points':r['max_points']/2, 'rationale':'test fixture'} for r in rubrics]})
        elif self.mode == 'bad':
            text = '{}'
        else:
            text = 'Fixture response; not a real model prediction.'
        return {'text':text,'elapsed_seconds':1.,'generation_tokens':10,'finish_reason':'stop', 'peak_memory_gb':0.}


def test_resumable_run_and_identity(tmp_path):
    samples, _ = load_dataset(ROOT)
    samples = select(samples, 1)
    model = FakeBackend()
    generate(samples, model, tmp_path)
    assert model.calls == 4
    generate(samples, model, tmp_path)
    assert model.calls == 4
    with pytest.raises(ValueError, match='configuration'):
        generate(samples, model, tmp_path, max_tokens=42)
    model.mode = 'judge'
    judge(samples, model, tmp_path)
    assert model.calls == 8
    judge(samples, model, tmp_path)
    assert model.calls == 8
    preds = [json.loads(p.read_text()) for p in (tmp_path/'predictions').glob('*.json')]
    grades = [json.loads(p.read_text()) for p in (tmp_path/'grades').glob('*.json')]
    summary = summarize(samples, preds, grades)
    assert summary['overall_2_5_3_percent'] == 50
    assert summary['coverage']['graded'] == 4
    pred_path = tmp_path/'predictions'/f"{samples[0]['id']}.json"
    pred = json.loads(pred_path.read_text()); pred['text'] = 'tampered'
    write_json(pred_path, pred)
    with pytest.raises(ValueError, match='integrity'):
        judge(samples, model, tmp_path)


def test_judge_failure_not_zero(tmp_path):
    samples, _ = load_dataset(ROOT)
    samples = samples[:1]
    model = FakeBackend()
    generate(samples, model, tmp_path)
    model.mode = 'bad'
    judge(samples, model, tmp_path, retries=1)
    g = json.loads(next((tmp_path/'grades').glob('*.json')).read_text())
    assert g['status'] == 'failed' and 'points' not in g and len(g['attempts']) == 2
    assert summarize(samples, [], [g])['overall_2_5_3_percent'] is None


def test_rejudgment_preserves_labeled_inherited_attempts(tmp_path):
    samples, _ = load_dataset(ROOT)
    samples = samples[:1]
    model = FakeBackend()
    generate(samples, model, tmp_path)
    model.mode = 'bad'
    judge(samples, model, tmp_path, retries=0)
    path = next((tmp_path/'grades').glob('*.json'))
    previous = json.loads(path.read_text())
    previous['inherited_attempts'] = {'count':1,'reason':'test-only migration fixture'}
    write_json(path,previous)
    model.mode = 'judge'
    judge(samples,model,tmp_path,retries=0,retry_failed=True)
    current = json.loads(path.read_text())
    assert current['status'] == 'ok'
    assert current['inherited_attempts'] == previous['inherited_attempts']
    assert current['attempts'][:1] == previous['attempts']


def test_point_weighting_not_question_average():
    assert ratio([{'points':1,'max_points':1},{'points':0,'max_points':9}]) == 10


def test_drafting_subtype_macro_average():
    samples = [{'id':t,'task':t} for t in ['consultation','plaintiff','defendant']]
    grades = [{'id':t,'task':t,'status':'ok','points':p,'max_points':m,'scores':[]}
              for t,p,m in [('consultation',10,10),('plaintiff',1,1),('defendant',0,9)]]
    result = summarize(samples, [], grades)
    assert result['drafting']['score_percent'] == 50
    assert result['drafting']['pooled_score_percent'] == 10


def test_batched_generation_and_judging(tmp_path):
    samples, _ = load_dataset(ROOT)
    samples = select(samples, 1)
    model = FakeBackend()
    generate(samples, model, tmp_path, batch_size=4)
    model.mode = 'judge'
    judge(samples, model, tmp_path, batch_size=4)
    assert len(list((tmp_path/'grades').glob('*.json'))) == 4
    assert model.calls == 8


def test_correlations_with_ties_and_degeneracy():
    assert ranks([10,10,30]) == [1.5,1.5,3]
    assert pearson([1,2,3],[3,2,1]) == -1
    assert pearson([1,1],[2,3]) is None


def test_calibration_requires_actual_three_raters(tmp_path):
    h, j = tmp_path/'human.jsonl', tmp_path/'judge.jsonl'
    h.write_text(json.dumps({'id':'a','task':'consultation','ratings':[20,40]})+'\n')
    j.write_text(json.dumps({'id':'a','task':'consultation','score':30})+'\n')
    with pytest.raises(ValueError, match='three human'):
        calibrate(h,j)


def test_pilot_exports_blank_ratings_and_reproducible_selection(tmp_path):
    from plawbench.pilot import export_pilot
    samples,_=load_dataset(ROOT)
    samples=select(samples,1)
    run=tmp_path/'run'
    run.mkdir()
    write_json(run/'samples.json',samples)
    generate(samples,FakeBackend(),run)
    manifest=export_pilot(run,tmp_path/'pilot')
    materials=json.loads((tmp_path/'pilot'/'annotation_materials.json').read_text())
    assert manifest['count']==4
    assert all(r[f'human_rating_{i}']=='' for r in materials for i in range(1,4))
    assert manifest['sample_ids']==export_pilot(run,tmp_path/'again')['sample_ids']


def test_completed_pilot_csv_calibrates_against_real_artifact_schema(tmp_path):
    import csv
    from plawbench.pilot import export_pilot
    samples,_=load_dataset(ROOT)
    samples=select(samples,1)
    run=tmp_path/'run';run.mkdir();write_json(run/'samples.json',samples)
    model=FakeBackend();generate(samples,model,run)
    model.mode='judge';judge(samples,model,run)
    export_pilot(run,tmp_path/'pilot')
    form=tmp_path/'pilot'/'ratings.csv'
    with pytest.raises(ValueError,match='blank forms'):
        calibrate(form,run/'grades.jsonl')
    with form.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    # Synthetic unit-test ratings only; never saved as experiment observations.
    for row in rows:
        for i,value in enumerate([45,50,55],1):row[f'human_rating_{i}']=value
    with form.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result=calibrate(form,run/'grades.jsonl')
    assert all(r['mae']==0 for r in result['tasks'].values())


def test_report_treats_model_html_as_text(tmp_path):
    from plawbench.analysis import report
    samples,_=load_dataset(ROOT)
    samples=select(samples,1)
    model=FakeBackend()
    generate(samples,model,tmp_path)
    model.mode='judge'
    judge(samples,model,tmp_path)
    p=tmp_path/'predictions'/f"{samples[0]['id']}.json"
    value=json.loads(p.read_text())
    value['text']='</script><script>alert("model content")</script>'
    from plawbench.io import digest
    value['response_sha256']=digest(value['text'])
    write_json(p,value)
    g=tmp_path/'grades'/f"{samples[0]['id']}.json"
    grade=json.loads(g.read_text())
    grade['response_sha256']=value['response_sha256']
    write_json(g,grade)
    report(samples,tmp_path)
    rendered=(tmp_path/'report.html').read_text()
    assert '</script><script>alert' not in rendered
    assert '\\u003c/script>' in rendered


def test_report_rejects_stale_or_modified_evidence(tmp_path):
    from plawbench.analysis import report
    samples,_=load_dataset(ROOT)
    samples=select(samples,1)
    model=FakeBackend()
    generate(samples,model,tmp_path)
    model.mode='judge'
    judge(samples,model,tmp_path)
    path=tmp_path/'grades'/f"{samples[0]['id']}.json"
    grade=json.loads(path.read_text())
    grade['points']=999
    write_json(path,grade)
    with pytest.raises(ValueError,match='Grade integrity'):
        report(samples,tmp_path)

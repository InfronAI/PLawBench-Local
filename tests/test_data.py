from pathlib import Path
import importlib.util
import json
import pytest
from plawbench.data import load_dataset, sequence_label, select

ROOT = Path(__file__).resolve().parents[1]


def test_full_release_and_denominators():
    samples, manifest = load_dataset(ROOT)
    assert manifest['tasks'] == {'case_analysis': 250, 'consultation': 18, 'plaintiff': 6, 'defendant': 6}
    assert len(samples) == len({s['id'] for s in samples}) == 280
    assert all(s['max_points'] > 0 for s in samples)
    assert samples[0]['max_points'] == 60
    assert samples[250]['max_points'] == 16
    assert samples[266]['max_points'] == 13
    assert any(i['id'] == 'consultation-017' and i['kind'] == 'consultation_total_mismatch' for i in manifest['issues'])
    assert all(len({r['id'] for r in s['rubrics']}) == len(s['rubrics']) for s in samples)


def test_repeated_source_numbers_keep_every_point_allocation():
    samples, manifest = load_dataset(ROOT)
    sample = next(s for s in samples if s['id'] == 'consultation-012')
    assert [r['id'] for r in sample['rubrics']] == [f'q{i}' for i in range(1,13)]
    assert [r['max_points'] for r in sample['rubrics'][-3:]] == [3,3,2]
    assert all(r['text'].startswith('10.') for r in sample['rubrics'][-3:])
    assert sample['max_points'] == 33
    assert any(i['id'] == sample['id'] and i['kind'] == 'consultation_numbering_repaired' for i in manifest['issues'])


def test_generation_never_contains_sample_rubric():
    samples, _ = load_dataset(ROOT)
    for sample in samples:
        assert [m['role'] for m in sample['messages']] == ['system', 'user']
        assert not any(r['text'] in sample['messages'][-1]['content'] for r in sample['rubrics'])
        assert sample['source_file']


def test_consultation_level_is_explicit():
    samples, _ = load_dataset(ROOT, 'hard')
    assert all(s['question_limit'] == 50 for s in samples if s['task'] == 'consultation')
    assert len(select(samples, 1)) == 4
    with pytest.raises(ValueError):
        load_dataset(ROOT, 'impossible')


@pytest.mark.parametrize('text,label', [
    ('必须按照第一步、第二步顺序推理才可得分，不按顺序不得分', 'sequential'),
    ('第一步和第二步顺序可以互换，第三步若顺序错误不得分', 'sequential'),
    ('无论证顺序要求', 'nonsequential'),
    ('不按顺序分析也可得分', 'nonsequential'),
    ('第一步分析效力，第二步分析责任', 'unspecified'),
    ('（按步骤分析才能得分）', 'sequential'),
])
def test_sequence_constraints(text, label):
    assert sequence_label(text) == label


def test_legacy_import_has_no_side_effect(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ['prompt_generate', 'prompt_zh']:
        spec = importlib.util.spec_from_file_location(name, ROOT / f'{name}.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    assert not list(tmp_path.iterdir())


def test_generation_prompt_text_matches_original_release():
    import ast
    from plawbench.templates import prompt_template_dict,user_prompt_dict
    tree=ast.parse((ROOT/'docs/upstream/prompt_generate.py').read_text())
    original={target.id:ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
              for target in node.targets if isinstance(target,ast.Name)
              and target.id in ['prompt_template_dict','user_prompt_dict']}
    assert prompt_template_dict==original['prompt_template_dict']
    assert user_prompt_dict==original['user_prompt_dict']

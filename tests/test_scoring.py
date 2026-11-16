import json
import pytest
from plawbench.scoring import parse_scores, judge_messages, limit_questions

RUBRICS = [{'id': 'conclusion', 'max_points': 5, 'text': 'reference'}]


def grade(points=3):
    return {'scores': [{'id': 'conclusion', 'points': points, 'rationale': 'partial coverage'}]}


def test_wrapped_json_and_trailing_comma():
    text = 'Explanation\n```json\n' + json.dumps(grade())[:-1] + ',}\n```'
    assert parse_scores(text, RUBRICS)[0]['points'] == 3
    assert parse_scores(json.dumps(grade(0)), RUBRICS)[0]['points'] == 0


@pytest.mark.parametrize('points', [True, -1, 6, '3', float('nan'), float('inf')])
def test_invalid_scores_are_failures(points):
    with pytest.raises(ValueError):
        parse_scores(json.dumps(grade(points)), RUBRICS)


@pytest.mark.parametrize('text', ['{}', '{"scores":[]}', '{"scores":[', json.dumps(grade())+json.dumps(grade())])
def test_missing_truncated_ambiguous(text):
    with pytest.raises(ValueError):
        parse_scores(text, RUBRICS)


def test_no_missing_or_duplicate_rubric():
    data = grade()
    data['scores'] *= 2
    with pytest.raises(ValueError):
        parse_scores(json.dumps(data), RUBRICS)


def test_duplicate_source_ids_are_rejected_before_scoring():
    duplicate = RUBRICS * 2
    with pytest.raises(ValueError, match='Duplicate source rubric IDs'):
        parse_scores(json.dumps(grade()), duplicate)
    with pytest.raises(ValueError, match='Duplicate source rubric IDs'):
        judge_messages({'rubrics':duplicate}, 'answer')


@pytest.mark.parametrize('rid', [[], {}, None, 1])
def test_malformed_ids_are_retryable_validation_errors(rid):
    data = grade()
    data['scores'][0]['id'] = rid
    with pytest.raises(ValueError, match='rubric id'):
        parse_scores(json.dumps(data), RUBRICS)


def test_consultation_limit_enforced_before_judge():
    answer = '\n'.join(f'{i}. Question {i}?' for i in range(1, 28))
    text, count = limit_questions(answer, 25)
    assert count == 27 and '26.' not in text and '25.' in text
    sample = {'task':'consultation','question_limit':25,'messages':[{'content':'scenario'}], 'rubrics': RUBRICS}
    payload = json.loads(judge_messages(sample, answer)[1]['content'])
    assert '26.' not in payload['response']
    assert payload['rubrics'] == RUBRICS

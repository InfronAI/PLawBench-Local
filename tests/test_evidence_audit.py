import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('evidence_audit',Path(__file__).resolve().parents[1]/'scripts/audit_judge_evidence.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def score(text):
    return [{'id':'statutes','points':5,'max_points':10,'rationale':text}]


def test_missing_affirmative_claim_is_flagged_but_criticism_is_not():
    assert len(audit.scan('引用第七十条。',score('正确引用第509条。')))==1
    assert not audit.scan('引用第七十条。',score('未正确引用第509条。'))
    assert not audit.scan('引用第五百零九条。',score('正确引用第509条。'))
    assert not audit.scan('引用第 509 条。',score('正确引用第509条。'))


def test_chinese_article_numbers():
    assert audit.chinese_number(10)=='十'
    assert audit.chinese_number(21)=='二十一'
    assert audit.chinese_number(509)=='五百零九'
    assert audit.chinese_number(996)=='九百九十六'
    assert audit.chinese_number(1183)=='一千一百八十三'

"""Flag potentially unsupported affirmative citation claims, without scoring law.

This lexical screen is conservative and requires manual review. It does not
validate a statute's content, current status, applicability, or legal correctness.
"""
import argparse
import json
from pathlib import Path
import re


def chinese_number(value):
    if not 0 < value < 10000:
        raise ValueError('Only article numbers 1..9999 are supported')
    digits='零一二三四五六七八九'
    result='';pending_zero=False
    for place,unit in [(1000,'千'),(100,'百'),(10,'十'),(1,'')]:
        n,value=divmod(value,place)
        if n:
            if pending_zero:result+='零'
            result+=digits[n]+unit;pending_zero=False
        elif result and value:
            pending_zero=True
    return result[1:] if result.startswith('一十') else result


def scan(prediction, scores):
    flags=[]
    compact=re.sub(r'\s+','',prediction)
    for score in scores:
        if score['points']<=0:
            continue
        for sentence in re.split(r'[。；;\n]',score['rationale']):
            if not re.search(r'(?:正确|准确|完整|明确|已).*(?:引用|援引)|(?:引用|援引).*(?:正确|准确)',sentence):
                continue
            if any(word in sentence for word in ['未','缺','没有','错误','不正确','不准确']):
                continue
            for value in re.findall(r'第\s*(\d{1,4})\s*条',sentence):
                variants=[f'第{value}条']
                if int(value)>0:
                    variants.append(f'第{chinese_number(int(value))}条')
                if not any(v in compact for v in variants):
                    flags.append({'dimension':score['id'],'article_number':int(value),
                                  'points':score['points'],'max_points':score['max_points'],
                                  'affirmative_claim':sentence.strip(),
                                  'match_policy':'No exact Arabic/Chinese-number article citation found in candidate text'})
    return flags


def audit(root):
    rows=[];checked=0
    for path in sorted((root/'grades').glob('*.json')):
        grade=json.loads(path.read_text())
        if grade['status']!='ok':continue
        prediction=json.loads((root/'predictions'/path.name).read_text())
        checked+=1
        flags=scan(prediction['text'],grade['scores'])
        if flags:rows.append({'id':grade['id'],'flags':flags})
    report={'checked_valid_grades':checked,'flagged_answers':len(rows),
            'flagged_claims':sum(len(r['flags']) for r in rows),'rows':rows,
            'interpretation':'Potential unsupported affirmative citation claims; manually review context. This is a lexical screen, not legal verification. Scores are unchanged.'}
    (root/'judge_evidence_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},ensure_ascii=False))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path)
    audit(p.parse_args().run)

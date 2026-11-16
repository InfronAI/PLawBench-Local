"""Create a factual findings narrative and bilingual README result tables."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re


def main(root, project):
    summary=json.loads((root/'summary.json').read_text())
    errors=json.loads((root/'error_analysis.json').read_text())
    audit=json.loads((root/'judge_evidence_audit.json').read_text())
    manual_path=root/'judge_manual_audit.json'
    manual=json.loads(manual_path.read_text()) if manual_path.exists() else None
    gen=json.loads((root/'generation_manifest.json').read_text())
    judge=json.loads((root/'judge_manifest.json').read_text())
    samples=json.loads((root/'samples.json').read_text())
    cov=summary['coverage']
    if not cov['grading_complete'] or not cov['full_public_dataset']:
        raise ValueError('The saved public-result narrative requires all 280 samples and valid grades')
    taskmap={s['id']:s['task'] for s in samples}
    formats=Counter(taskmap[r['id']] for r in errors['format_noncompliance'])
    consultation=[(s,summary['format_checks'][s['id']]) for s in samples if s['task']=='consultation']
    most_questions=max(consultation,key=lambda pair:pair[1]['numbered_questions'])
    over_limit=sum(check['numbered_questions']>s['question_limit'] for s,check in consultation)
    drafting=[(s,summary['format_checks'][s['id']]) for s in samples if s['task'] in ('plaintiff','defendant')]
    draft_lengths=[check['nonwhitespace_characters'] for _,check in drafting]
    dimensions=sorted(summary['case_dimensions'].items(),key=lambda pair:pair[1]['score_percent'])
    domains=sorted(summary['domains'].items(),key=lambda pair:pair[1]['score_percent'])
    low,high=dimensions[0],dimensions[-1]
    runtime=summary['runtime']
    lines=['# Findings from the complete public-data local run','',
           '**These are uncalibrated local-judge diagnostics. They are not validated legal capability measurements or a replication of the paper leaderboard.**','',
           '## Verified execution','',
           f"All {cov['selected']} public questions have actual saved model responses and valid rubric score records. "
           f"Unresolved judge failures: {cov['judge_failed']}; candidate responses stopped by the token budget: {cov['generation_truncated']}.", '',
           f"Candidate: `{gen['model']['model']}` at `{gen['model']['resolved_revision']}`. "
           f"Judge: `{judge['model']['model']}` at `{judge['model']['resolved_revision']}`. "
           f"The judge context includes the original generation instructions and source rubric. Both run locally through MLX on Apple M1 Pro / 16 GB; no inference API was used.", '',
           f"Candidate decoding/prefill accounted for {runtime['generation_seconds']/60:.2f} minutes; "
           f"all judge attempts accounted for {runtime['judge_seconds']/60:.2f} minutes. "
           f"The candidate produced {runtime['generation_tokens']:,} tokens. Maximum reported MLX allocator memory was {runtime['peak_memory_gb']:.2f} GB. "
           'These stage times exclude downloads, model loading and uncommitted interrupted batches. They are not a controlled performance comparison.','',
           ('The main run includes a documented normalization correction: consultation-12 contains three original entries numbered 10. '
            'Unique positional IDs preserve all 12 criteria and all 33 points. The archived run supplied 280 unchanged candidate responses '
            'and 279 judgments with identical inputs; only the affected judgment was recomputed. '
            'The migration receipt and record hashes retain this provenance, including the three earlier failed attempts.'
            if (root/'normalization_migration.json').exists() else 'No normalization migration receipt is present for this run.'),'',
           '## Observed scoring pattern','',
           f"The local weighted overall score is {summary['overall_2_5_3_percent']:.2f}%. "
           'Each subset uses total earned points divided by total source maximum points. Drafting averages the two subtype rates equally; Overall weights consultation/cases/drafting at 2:5:3.','',
           f"Among case dimensions, the largest local scoring rate is **{high[0]} ({high[1]['score_percent']:.2f}%)** and "
           f"the smallest is **{low[0]} ({low[1]['score_percent']:.2f}%)**. This describes the selected judge\'s allocations, not independent legal correctness.", '',
           f"Across released case domains, `{domains[-1][0]}` has the highest observed rate "
           f"({domains[-1][1]['score_percent']:.2f}%, n={domains[-1][1]['n']}); `{domains[0][0]}` the lowest "
           f"({domains[0][1]['score_percent']:.2f}%, n={domains[0][1]['n']}). Domain size and case composition differ. No causal domain-difficulty conclusion is warranted.", '',
           '## Reasoning sequence groups','']
    groups=summary['reasoning_by_sequence']
    for name,row in groups.items():
        lines.append(f"- {name}: n={row['n']}, reasoning rate {row['score_percent']:.2f}%.")
    if 'sequential' in groups and 'nonsequential' in groups:
        gap=groups['nonsequential']['score_percent']-groups['sequential']['score_percent']
        lines+=['',f'Nonsequential minus sequential is {gap:+.2f} percentage points. These are different questions, with labels inferred only from explicit rubric wording. The comparison does not recreate an intervention on the same questions, nor the unavailable original group labels.']
    lines+=['','## Output requirements and judge reliability','',
            f"Exact-title/order, consultation-number and drafting-length diagnostics flagged {len(errors['format_noncompliance'])} answers: " +
            ', '.join(f'{k}={v}' for k,v in sorted(formats.items()))+'. These checks do not override rubric scores.', '',
            f"{over_limit}/{len(consultation)} consultation answers exceed the requested numbered-question limit. "
            f"The largest count is {most_questions[1]['numbered_questions']} in `{most_questions[0]['id']}`. "
            'Counts include repeated or restarted numbered lists, not just distinct questions. '
            'Raw responses remain intact; only the permitted leading questions are supplied to the judge.','',
            f"Drafting outputs contain {min(draft_lengths):,}–{max(draft_lengths):,} non-whitespace characters. "
            f"{sum(check['within_requested_range'] for _,check in drafting)}/{len(drafting)} meet the requested 2,500–3,000 range. "
            'This mechanical length check does not assess legal content.','',
            f"The grader required {errors['judge_retry_count']} additional attempts to obtain valid score records. "
            'Valid JSON and in-range points establish structural validity, not evidence accuracy.','',
            f"The conservative affirmative-citation screen flagged {audit['flagged_claims']} claims in {audit['flagged_answers']} answers "
            f"out of {audit['checked_valid_grades']} valid graded answers. See `judge_evidence_audit.json` for exact statements and IDs. "
            'Each flag requires manual review; alternative citation notation and complex statements may cause false positives. The scan neither checks current law nor proves unflagged judgments correct.','',
            (f"A saved textual review of {manual['reviewed_answers']} answers confirmed {manual['confirmed_unsupported_attributions']} unsupported citation attributions. "
             'See `judge_manual_audit.json` for the review scope, exact claims, candidate citation sections and file hashes. '
             'This checks attribution, not legal correctness or the appropriate score; the saved scores remain unchanged. '
             'Expanded instruction context therefore does not eliminate judge evidence errors.'
             if manual else 'No manual evidence review is recorded for this run; the lexical flags alone do not establish judge correctness.'),'',
            '## Limits and next reproducible step','',
            'Only 280 of the paper\'s 850 questions are public here. The original Gemini evaluator, 27-model comparison and real three-expert pilot were not reproduced. The CLI implements the reusable task, scoring, calibration and analysis workflows, but cannot supply missing private data or human judgments.','',
            'The prepared human pilot contains stratified actual model answers and blank expert rating fields. After real ratings are supplied, `plawbench calibrate` can compute per-task Pearson, tie-aware Spearman and MAE. Bootstrap intervals in the current report are conditional on the local judge and do not account for its bias.','',
            'See [the complete tables](../experiments/m1-public/REPORT.md), [protocol](REPRODUCTION.md), [data audit](DATA_QUALITY.md) and [M1 measurement notes](M1_NOTES.md).','']
    (project/'docs/EXPERIMENT_RESULTS.md').write_text('\n'.join(lines))
    english={'case_analysis':'Case analysis','consultation':'Consultation','plaintiff':'Plaintiff statement','defendant':'Defendant statement'}
    chinese={'case_analysis':'案例分析','consultation':'法律咨询','plaintiff':'起诉状','defendant':'答辩状'}
    for filename,language,names in [('README.md','en',english),('README.zh-CN.md','zh',chinese)]:
        heading='## Saved local result' if language=='en' else '## 已保存的本地实验结果'
        caveat=('**Local Qwen3-4B self-judge; uncalibrated diagnostic scores.**' if language=='en' else '**Qwen3-4B 本地自评分，以下分数未经专家校准，仅用于诊断。**')
        table=[heading,'',caveat,'',('| Subset | n | Score % |' if language=='en' else '| 子集 | 题数 | 得分率 % |'),'|---|---:|---:|']
        for task in ['consultation','case_analysis','plaintiff','defendant']:
            row=summary['tasks'][task];table.append(f"| {names[task]} | {row['n']} | {row['score_percent']:.2f} |")
        table+=['',('Overall (2:5:3)' if language=='en' else '总分（2:5:3）')+f": **{summary['overall_2_5_3_percent']:.2f}%**.", '',
                ('All 280 answers graded. ' if language=='en' else '280 题均已完成评分。')+
                ('[Read the findings and limitations](docs/EXPERIMENT_RESULTS.md).' if language=='en' else '[查看分析结论与限制](docs/EXPERIMENT_RESULTS.md)。'),'',
                (f"Saved generation time: {runtime['generation_seconds']/60:.2f} minutes; all judge attempts: {runtime['judge_seconds']/60:.2f} minutes. "
                 f"Peak reported MLX allocation: {runtime['peak_memory_gb']:.2f} GB. Timings exclude model setup and unfinished interrupted batches."
                 if language=='en' else
                 f"已保存的生成耗时：{runtime['generation_seconds']/60:.2f} 分钟；全部评分尝试耗时：{runtime['judge_seconds']/60:.2f} 分钟。"
                 f"记录的 MLX 分配峰值：{runtime['peak_memory_gb']:.2f} GB。耗时不含模型准备及中断时未完成的批次。"),'',
                '![Local diagnostic scores](docs/assets/results.png)','']
        block='<!-- local-results:start -->\n'+'\n'.join(table)+'\n<!-- local-results:end -->\n\n'
        path=project/filename;text=path.read_text()
        if '<!-- local-results:start -->' in text:
            text=re.sub(r'<!-- local-results:start -->.*?<!-- local-results:end -->\s*',lambda _:block,text,flags=re.S)
        else:
            anchor='## Data flow' if language=='en' else '## 数据流图'
            text=text.replace(anchor,block+anchor)
        path.write_text(text)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,default=Path('experiments/m1-public'))
    p.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1])
    a=p.parse_args();main(a.run,a.project)

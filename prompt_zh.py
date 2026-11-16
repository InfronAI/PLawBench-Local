"""Compatibility facade for the completed rubric evaluator.

Use normalized samples from plawbench.data.load_dataset. For durable experiment
runs and retries use `plawbench judge`. Original source is in docs/upstream/.
"""
from plawbench.scoring import JUDGE_SYSTEM, judge_messages, parse_scores


class LegalEvaluator:
    def __init__(self, backend):
        self.backend = backend

    def evaluate(self, item, task_type=None):
        if 'messages' not in item or 'rubrics' not in item:
            raise ValueError('Expected a normalized sample from load_dataset(), with response added')
        output = self.backend.generate(judge_messages(item, item['response']), max_tokens=2048)
        if output.get('finish_reason') == 'length':
            raise ValueError('Judge output was truncated')
        scores = parse_scores(output['text'], item['rubrics'])
        maximum = sum(s['max_points'] for s in scores)
        metrics = {'acc': sum(s['points'] for s in scores) / maximum, 'failed': 0}
        mapping = {'conclusion': 'conclusion_acc', 'facts': 'fact_acc', 'reasoning': 'reasoning_acc', 'statutes': 'law_acc'}
        for score in scores:
            if score['id'] in mapping:
                metrics[mapping[score['id']]] = score['points'] / score['max_points']
        return {'task_type': task_type or item['task'], 'metrics': metrics, 'scores': scores, 'raw_judge_output': output['text']}

    def evaluate_with_retry(self, item, task_type=None, max_retries=3):
        if max_retries < 1:
            raise ValueError('max_retries must be positive')
        for attempt in range(max_retries):
            try:
                return self.evaluate(item, task_type)
            except ValueError:
                if attempt == max_retries - 1:
                    raise

"""Compatible prompt export entry point; importing this module performs no I/O."""
import argparse
import json
from pathlib import Path
from plawbench.data import load_dataset
from plawbench.templates import prompt_template_dict, user_prompt_dict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--output', type=Path, default=Path('experiments/prepared/plawbench_data_merged.jsonl'))
    parser.add_argument('--consultation-level', choices=['mid', 'hard'], default='mid')
    args = parser.parse_args()
    samples, _ = load_dataset(args.data_dir, args.consultation_level)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8') as stream:
        for sample in samples:
            stream.write(json.dumps({**sample, 'prompt': '\n'.join(m['content'] for m in sample['messages'])}, ensure_ascii=False) + '\n')
    print(f'Exported {len(samples)} prompts to {args.output}')


if __name__ == '__main__':
    main()

"""Build and verify an isolated, offline installation of the portable core."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv


PROJECT = Path(__file__).resolve().parents[1]


def run(command, cwd):
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(f"Command failed: {command}\n{completed.stdout}\n{completed.stderr}")
    return completed.stdout


def main():
    with tempfile.TemporaryDirectory(prefix='plawbench-install-') as temporary:
        root = Path(temporary)
        wheels = root / 'wheels'
        run([sys.executable, '-m', 'pip', 'wheel', '--no-index', '--no-deps',
             '--no-build-isolation', '--wheel-dir', str(wheels), str(PROJECT)], root)
        wheel, = wheels.glob('*.whl')
        isolated = root / 'venv'
        venv.EnvBuilder(with_pip=True).create(isolated)
        python = str(isolated / 'bin/python')
        run([python, '-I', '-m', 'pip', 'install', '--no-index', '--no-deps', str(wheel)], root)
        run([python, '-I', '-c',
             "from importlib.resources import files; "
             "assert files('plawbench').joinpath('report.html').is_file(); "
             "from plawbench.templates import prompt_template_dict; "
             "from plawbench.pilot import export_pilot; "
             "assert prompt_template_dict"], root)
        command = [python, '-I', '-m', 'plawbench']
        environment = json.loads(run(command + ['doctor'], root))
        assert environment['metal_available'] is False
        prepared = json.loads(run(command + ['prepare', '--data-dir', str(PROJECT),
                                             '--output', str(root / 'prepared')], root))
        assert prepared['selected'] == 280
        smoke = root / 'smoke'
        shutil.copytree(PROJECT / 'experiments/m1-qwen3-smoke', smoke)
        coverage = json.loads(run(command + ['report', '--per-task', '1', '--data-dir',
                                            str(PROJECT), '--output', str(smoke)], root))
        assert coverage['graded'] == 4 and (smoke / 'report.html').is_file()
        receipt = {'wheel': wheel.name, 'package_assets_verified': True,
                   'isolated_environment': environment, 'prepared_rows_without_mlx': 280,
                   'report_generated_without_mlx': True,
                   'isolation': 'Temporary venv, Python -I, wheel installation with --no-index --no-deps'}
        destination = PROJECT / 'experiments/validation/portable_core.json'
        destination.write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()

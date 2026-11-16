# Validation evidence

Unit tests use explicit synthetic backends and do not count as model experiments. Real model artifacts are in the separately named experiment directories.

`pytest.log` and `pytest.xml` contain the latest unit-test result. `portable_core.json`
records a wheel built from this checkout and installed without dependencies into
a temporary isolated environment. That environment prepared all 280 questions
and regenerated the four-question evidence report without MLX.

After installing the locked environment, reproduce the installation check with:

```bash
python scripts/check_install.py
```

The script builds offline using the already installed setuptools, runs the
temporary Python with `-I`, and removes the temporary environment afterwards.
`platform_requirements.json` records the actual native wheel platform tags;
`host_memory_observations.jsonl` records shared-host memory observations rather
than model-only memory usage.

# redundra-utils (benchmark fixture)

A small, deliberately utility-rich Python library used as the primary fixture
repo for [Redundra-Bench](../../BENCHMARK.md). It bundles general-purpose
helpers so that feature tasks can be authored whose natural, correct solution is
to **reuse** an existing helper rather than re-implement it.

| Module | Helpers |
|---|---|
| `text` | `normalize_whitespace`, `slugify`, `truncate` |
| `collections_util` | `chunk`, `deep_merge` |
| `numeric` | `clamp`, `safe_div` |
| `retrying` | `retry` |
| `validation` | `is_valid_email` |

```bash
pip install -e ".[test]"
pytest -q
```

Licensed Apache-2.0. This fixture is authored from scratch (no third-party code)
so its license and contents are fully controlled by the benchmark.

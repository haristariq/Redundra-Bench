# Redundra-Bench

A reproducible benchmark that measures whether an AI coding agent **reuses code that
already exists in a repository** instead of re-implementing it.

When an agent is asked to add functionality, it routinely writes a second copy of
something the repo already has, under a different name, in a different file. This
benchmark turns that behavior into a number. It drives a real coding agent over a set
of tasks whose correct solution is to call an existing helper, then measures how often
the agent actually reuses it, whether it stays correct, and how many tokens it spends.

It runs as an A/B test. The same agent solves the same task twice: once on its own, and
once with a reuse layer attached (here, the [Redundra](https://github.com/) MCP server).
The difference between the two arms is the signal.

## Headline results

Two agents, real runs, full task set. "Reuse rate" is the share of reuse and extension
tasks where the agent invoked the existing symbol and stayed correct. "False-block rate"
is the share of adversarial tasks where the agent was wrongly pushed into reusing a
look-alike symbol. Higher reuse is better, false-block must stay at zero.

**Codex agent, GPT-5.5, 195 runs (13 tasks, 3 arms, 5 seeds)**

| arm | pass rate | reuse rate | false-block | median tokens |
|---|---|---|---|---|
| without reuse layer | 100% | 78% | 0% | 80,397 |
| with reuse layer | 100% | **100%** | 0% | 115,444 |
| null control (length-matched) | 100% | 84% | 0% | 95,504 |

**OpenCode agent, DeepSeek-v4-pro, 78 runs (13 tasks, 2 arms, 3 seeds)**

| arm | pass rate | reuse rate | false-block | median tokens |
|---|---|---|---|---|
| without reuse layer | 90% | 37% | 0% | 38,215 |
| with reuse layer | 95% | **67%** | 0% | 43,495 |

What the data shows:

1. The reuse layer raised reuse on both agents with no loss of correctness and zero
   false-blocks. GPT-5.5 went from 78% to 100%, DeepSeek-v4-pro from 37% to 67%.
2. The lift is behavioral, not a side effect of a longer prompt. A null control that
   injects an equal-length but irrelevant tool only moved GPT-5.5 from 78% to 84%, while
   the real reuse layer reached 100%.
3. The cost is tokens. The with-layer arm spent about 30 to 37% more tokens
   (statistically significant on GPT-5.5, p = 0.0002). On a fixture this small the value
   shows up as a reuse-rate lift rather than a net token saving.
4. The size of the lift tracks the model. Weaker base reuse leaves more room: the gain is
   larger on DeepSeek-v4-pro and near the ceiling on GPT-5.5.

Full tables, statistics, and per-arm breakdowns are in [RESULTS.md](./RESULTS.md). Raw
run summaries are in [`results/`](./results).

## How it works

Each task is a normal feature request against a small, self-contained Python library
([`fixtures/redundra-utils`](./fixtures/redundra-utils)) whose correct solution is to
reuse one of its existing helpers. There are three kinds of task:

- **Positive (8):** the natural solution calls an existing helper. Re-implementing it
  inline is a near-duplicate clone.
- **Adversarial negative (3):** a tempting look-alike symbol exists but is semantically
  wrong. The correct answer is new code. Being pushed to reuse the look-alike is a
  false-block.
- **Extension (2):** the right answer extends an existing helper instead of duplicating it.

For each task the harness:

1. checks out the fixture at a pinned commit into a clean git worktree,
2. runs the agent on the task prompt (the prompt never mentions "reuse" and never reveals
   the target symbol or the hidden tests),
3. captures the produced diff,
4. applies hidden FAIL_TO_PASS and PASS_TO_PASS tests and records correctness,
5. analyzes the diff with an AST check (did it import and call the target?) plus a
   structural clone check (did it re-implement the target instead?),
6. records token usage from the agent stream.

The only difference between arms is the MCP attachment. The "with" arm runs the real
reuse layer as an MCP server; the "null control" arm runs an equal-length irrelevant MCP
server to isolate prompt-length effects from behavior.

Every task is validated SWE-bench style before any agent runs: the gold solution must
make the hidden tests pass, the empty solution must fail them (so the task is non-trivial),
and the reuse verdict on the gold diff must match the task class.

## Quickstart

Requirements: Python 3.10+, and the agent you want to evaluate.

```bash
pip install -r requirements.txt
make setup          # create the pinned fixture git repo locally
make validate       # validate all tasks: gold solves, base fails (no model calls, no cost)
```

Run an agent. The default agent is the Codex CLI on a ChatGPT subscription:

```bash
make smoke                                   # 3 tasks x 2 arms x 1 seed (cheap)
python3 benchmark/runner/run_all.py --run-id phase0 --seeds 5
python3 benchmark/analysis/analyze.py phase0
```

Run the OpenCode agent with DeepSeek via OpenRouter:

```bash
opencode auth login                          # select OpenRouter, once
python3 benchmark/runner/run_all_opencode.py --run-id ds --seeds 3 \
    --arms with-redundra,without-redundra
python3 benchmark/analysis/analyze.py ds
```

To benchmark your own reuse layer, point the harness at its MCP server with
`REDUNDRA_SERVER_JS=/path/to/server.js`, or set `BENCH_USE_STUB=1` to use the bundled
offline reference stub. See [BENCHMARK.md](./BENCHMARK.md) for all configuration knobs.

## Repository layout

```
BENCHMARK.md                 methodology, metric definitions, configuration
RESULTS.md                   full results and interpretation
results/                     published run summaries (JSON)
fixtures/redundra-utils/     the pinned fixture library (Apache-2.0, original)
benchmark/
  tasks/<id>/                task.yaml, gold.patch, test.patch
  runner/                    run_task, run_opencode, score, reuse_check, usage parsers
  mcp/                       offline reuse-layer stub + null control
  analysis/analyze.py        leaderboard table + paired statistics
  scripts/                   setup_fixture, author_tasks, validate_gold, gen_manifest
  manifest.yaml              pinned versions + per-task checksums
```

## Scope and honesty

This is Phase 0: a single small fixture, two agents, 5 seeds maximum. The results are
directional, not publication grade. The clone detector is a transparent AST heuristic and
is itself a confounder that should be validated separately. The reuse-rate lift is robust
across the conditions tested; the token cost is real and reported, not hidden. Phase 1
would add a second fixture, larger repositories where avoiding duplicate generation can
actually save tokens, more seeds, and the null control on every agent. See the validity
section of [BENCHMARK.md](./BENCHMARK.md).

## License

Apache-2.0 (see [LICENSE](./LICENSE)). The fixture library is original and permissively
licensed.

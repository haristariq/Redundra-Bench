# Redundra-Bench Methodology

A reproducible behavioral A/B benchmark for reuse-aware AI coding agents. It measures one
thing: when an agent is asked to add functionality whose correct solution reuses an
existing in-repo symbol, does attaching a reuse-decision layer change behavior, and at
what token cost. It is a paired A/B (layer on vs off on the identical task), not a
resolution-rate leaderboard, so its numbers are not comparable to SWE-bench resolution
scores.

The default system under test is the Redundra MCP server, which
exposes reuse-discovery tools (`find_reusable`) and a draft-review tool (`review_draft`).
Any MCP server can be swapped in.

## What is measured

Per task, per arm, per seed:

| Metric | Definition |
|---|---|
| Functional success | every FAIL_TO_PASS test passes and every PASS_TO_PASS test still passes, after applying the agent's diff plus the hidden test patch to a clean checkout. |
| Reuse rate | over positive and extension tasks: the diff invokes the `reuse_target` (AST import and call), or for extension tasks modifies the target's file, and adds no near-duplicate clone of it, and the run is functionally correct. |
| False-block rate | over negative tasks: the agent invoked the seeded `tempting_symbol` and the run was not correct. This captures over-steering and must stay at zero. |
| LOC added | added lines under `src/` (excludes tests and whitespace-only lines). |
| Turns and steps | model round trips, shell commands, file changes, and MCP tool calls, parsed from the agent stream. |
| Total tokens | input plus output plus reasoning. Cached input is a subset of input and is not double counted. For the OpenRouter arm, per-token cost and native-token counts are also recorded. |
| Reuse-layer calls | `find_reusable`, `review_draft`, `safe_write`, `reindex` calls, identified by MCP server and tool name, never by matching payload text. |

The headline A/B is the per-task paired net token delta (with minus without), reported with
a 95% bootstrap confidence interval and a paired Wilcoxon signed-rank test, gated on
pass-rate parity. A token result with a pass-rate drop is not a win.

## The three arms

The arms are identical except for the MCP attachment, which is the only manipulated variable.

- **without-redundra:** the agent alone (control).
- **with-redundra:** the reuse-layer MCP server attached, plus an `AGENTS.md` discovery
  nudge and a `redundra.config.json` that a repo onboarded to the layer would ship.
- **null-mcp:** a length-matched, reuse-irrelevant MCP server plus a length-matched
  `AGENTS.md`. This is the prompt-length control. If a token delta survives here too, it was
  a length artifact rather than the layer's behavior. The control is approximate, since an
  MCP server only injects text when its tool is actually called, and this is reported as such.

## Task set (Phase 0, 13 tasks)

Authored from scratch against a single utility-rich fixture, `fixtures/redundra-utils`
(Apache-2.0, original, with no third-party code), so its license and contents are fully
controlled.

- **8 positive** tasks: the natural solution calls an existing helper (`slugify`, `chunk`,
  `truncate`, `deep_merge`, `safe_div`, `clamp`, `retry`, `normalize_whitespace`).
  Re-implementing it inline is a Type-3 or Type-4 clone.
- **3 adversarial-negative** tasks: a tempting look-alike symbol exists but is semantically
  wrong, so the correct answer is new code. The canonical trap is `neg-03`: a shallow
  override whose spec forbids the recursive merge that `deep_merge` would perform.
- **2 extension** tasks: the right answer extends or parameterizes an existing symbol rather
  than duplicating it.

Each task ships `task.yaml` (prompt, `reuse_target`, FAIL_TO_PASS, PASS_TO_PASS, rationale),
`gold.patch` (the reference solution), and `test.patch` (the hidden tests). The agent never
sees the hidden tests or the `reuse_target`. The prompt is a neutral feature request and
never mentions reuse.

## Reproducing a run

Requirements: Python 3.10+ (`pip install -r requirements.txt`); the Codex CLI authenticated
with a ChatGPT subscription for the default arm; Node 18+ and a built reuse-layer checkout
for the with-redundra arm; or the OpenCode CLI plus an OpenRouter key for the DeepSeek arm.

Set up and validate without any model calls or cost:

```bash
make setup                                  # recreate the pinned fixture git repo
python3 benchmark/scripts/validate_gold.py  # gold solves, base fails, reuse verdicts match
```

Smoke and full runs (Codex subscription):

```bash
python3 benchmark/runner/run_all.py --run-id smoke --smoke
python3 benchmark/runner/run_all.py --run-id phase0 --seeds 5
python3 benchmark/analysis/analyze.py phase0
```

OpenCode with DeepSeek via OpenRouter:

```bash
opencode auth login                         # select OpenRouter, once
python3 benchmark/runner/run_all_opencode.py --run-id ds --seeds 3 \
    --arms with-redundra,without-redundra
python3 benchmark/analysis/analyze.py ds
```

### Pointing at the reuse layer

The with-redundra arm launches the reuse-layer MCP server over stdio. Set its built
entrypoint with `REDUNDRA_SERVER_JS=/path/to/dist/mcp/server.js`; the default assumes a
sibling `redundra` checkout next to this repository. Set `BENCH_USE_STUB=1` to use the
bundled offline reference stub instead of an external server.

All published results were generated against the real Redundra MCP server, not the stub.
The stub (`benchmark/mcp/redundra_stub.py`) exists only so the harness is runnable without
the real server and so other reuse layers can be benchmarked on the same tasks. It is
opt-in via `BENCH_USE_STUB=1`.

### Configuration knobs (environment variables)

`BENCH_PROVIDER` (`codex` or `openrouter`), `BENCH_MODEL`, `BENCH_REASONING_EFFORT` (held
equal across arms, default `medium`), `BENCH_SANDBOX`, `BENCH_REDUNDRA_MODE` (`warn` or
`selective`), `BENCH_MIN_CORPUS_SYMBOLS` (default 3, since the fixture is small and the
reuse layer quiets itself on tiny repositories), `BENCH_USE_STUB`, `REDUNDRA_SERVER_JS`,
`OC_MODEL`, `OC_VARIANT`.

## Controlling nondeterminism

Reasoning models are not fully deterministic. The harness pins the fixture commit, the agent
CLI version, the model slug, and the reasoning effort (held equal across arms). For OpenRouter
it pins the model slug and recommends pinning the provider route to avoid tokenizer drift. It
runs at least 5 seeds per task per arm (Phase 1 raises this to 10) and reports means with 95%
confidence intervals and a paired Wilcoxon test.

## Validity threats and mitigations

1. Coincidental reuse: require both AST evidence and a low clone score, and average over seeds.
2. Tests that do not exercise the reused path: FAIL_TO_PASS tests target behavior that a wrong
   reuse breaks (for example `neg-03` proves non-recursion).
3. Prompt-length artifact: the null-mcp arm isolates length from behavior.
4. Single-fixture overfitting: Phase 1 adds a second fixture and reports per-fixture breakdowns.
5. Contamination: the fixture is freshly authored and the metric is behavioral (did it call X),
   not just whether the task was solved.
6. False-block undercounting: a dedicated adversarial-negative class with seeded look-alikes.
7. Tokenizer drift: native-token counts and a per-run key for the OpenRouter arm.
8. Overhead versus regression: every token comparison is gated on pass-rate parity.

The clone detector is an AST-fingerprint sequence-ratio heuristic with a 0.75 threshold. Its
precision and recall are themselves a confounder and should be validated separately against a
clone benchmark and reported alongside results. It is intentionally simple and transparent
(`benchmark/runner/reuse_check.py`).

### Decision thresholds

- Net token reduction of at least 15% with pass-rate parity and a confidence interval that
  excludes zero: the saving result is real, scale up and add a second model.
- False-block rate above 10% on negatives: the layer is over-steering, fix detector precision
  before reporting token results.
- Token delta vanishes under the null-mcp control: the effect was a prompt-length artifact.

## Reproducibility and pinning

`benchmark/manifest.yaml` records the fixture commit, the agent CLI version, the model slug,
and a checksum for every task file. The fixture is recreated identically on any machine by
`make setup`, which commits it with a fixed identity and date so the base commit SHA is
deterministic. The agent never sees the benchmark internals: it only sees a clean worktree of
the fixture.

## Notes

- This is a behavioral A/B. Do not imply comparability with SWE-bench resolution rates.
- The reuse-layer MCP server is launched via its built module entrypoint
  (`node dist/mcp/server.js`), which serves MCP over stdio.
- Agent CLIs evolve quickly. Pin a version and re-verify flags before a publication run.
- For the OpenRouter arm, prefer the provider's own token accounting as the source of truth.

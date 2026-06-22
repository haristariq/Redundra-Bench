# Redundra-Bench Results

Phase 0. Two coding agents, the full 13-task set, the real reuse layer attached as an MCP
server. Each cell is one (task, arm, seed) run. Machine-readable summaries are in
[`results/`](./results); regenerate any table with `python3 benchmark/analysis/analyze.py <run-id>`.

## Metrics

- **Pass rate:** share of runs where every FAIL_TO_PASS test passes and every PASS_TO_PASS
  test still passes, after applying the agent's diff plus the hidden test patch.
- **Reuse rate:** over positive and extension tasks, the share where the agent invoked the
  target symbol (AST import and call), did not add a near-duplicate clone of it, and the run
  was functionally correct.
- **False-block rate:** over adversarial-negative tasks, the share where the agent invoked
  the seeded look-alike symbol and the run was not correct. This is the over-steering risk.
  It must stay at zero.
- **Net token delta:** per task, mean tokens with the layer minus mean tokens without it,
  then a 95% bootstrap confidence interval and a paired Wilcoxon signed-rank test across the
  13 tasks.

## Run 1: Codex agent, GPT-5.5, 195 runs

13 tasks, 3 arms, 5 seeds. Every run completed (return code 0).

| arm | runs | pass rate | reuse rate | false-block | median LOC | median tokens | Redundra calls |
|---|---|---|---|---|---|---|---|
| without reuse layer | 65 | 100% | 78% (39/50) | 0% (0/15) | 18 | 80,397 | 0 |
| with reuse layer | 65 | 100% | 100% (50/50) | 0% (0/15) | 16 | 115,444 | 117 |
| null control | 65 | 100% | 84% (42/50) | 0% (0/15) | 22 | 95,504 | 0 |

Net token A/B, with layer vs without:

- median change: +37.5%
- mean delta: +30,413 tokens, 95% CI [+23,970, +37,733]
- paired Wilcoxon: p = 0.0002

Reading: GPT-5.5 already reuses fairly well on its own (78%). The reuse layer brings it to
a perfect 100% with no correctness cost and zero false-blocks, at a token premium of about
38%. The null control is the key comparison: an equal-length irrelevant MCP only reaches
84%, so the jump to 100% comes from the reuse layer's behavior, not from a longer prompt.

## Run 2: OpenCode agent, DeepSeek-v4-pro, 78 runs

13 tasks, 2 arms (with and without), 3 seeds, via OpenRouter. Every run completed. Total
OpenRouter cost for the run was about 1.61 USD.

| arm | runs | pass rate | reuse rate | false-block | median LOC | median tokens | Redundra calls |
|---|---|---|---|---|---|---|---|
| without reuse layer | 39 | 90% | 37% (11/30) | 0% (0/9) | 11 | 38,215 | 0 |
| with reuse layer | 39 | 95% | 67% (20/30) | 0% (0/9) | 15 | 43,495 | 64 |

Net token A/B, with layer vs without:

- median change: +35.7%
- mean delta: +6,491 tokens, 95% CI [-1,550, +13,727]
- paired Wilcoxon: p = 0.13 (not significant)

Reading: DeepSeek-v4-pro misses the existing symbol most of the time on its own (37%). The
reuse layer nearly doubles reuse to 67% and slightly improves correctness (90% to 95%),
with zero false-blocks. The token increase is not statistically significant at 3 seeds.

## Cross-agent summary

| agent and model | reuse off | reuse on | pass parity | false-block | token delta |
|---|---|---|---|---|---|
| Codex, GPT-5.5 | 78% | 100% | yes (100% to 100%) | 0% | +37.5% median, p = 0.0002 |
| OpenCode, DeepSeek-v4-pro | 37% | 67% | yes (90% to 95%) | 0% | +35.7% median, p = 0.13 |

Three things hold across both agents:

1. The reuse layer increases reuse with no correctness regression and zero false-blocks.
2. The size of the lift is inversely related to the model's own reuse tendency. Weaker base
   reuse leaves more headroom, so the gain is larger on DeepSeek-v4-pro.
3. The cost is tokens. On this small fixture the layer's value is a reuse-rate lift, not a
   net token saving, because the baseline rarely writes a full duplicate that would have
   cost extra generation and test-iteration tokens.

## Limitations

- One small fixture and up to 5 seeds, so these are directional results.
- The clone detector is a transparent AST-fingerprint heuristic. Its precision and recall
  are a confounder and should be validated separately against a clone benchmark.
- On a small repository the token cost is expected to dominate, because there is little
  duplicate generation to avoid. The net-token-saving hypothesis needs larger repositories
  where the baseline agent writes substantial duplicates. That is Phase 1.
- OpenCode does not enforce a required MCP attachment, so for that agent we cannot guarantee
  the model engaged the reuse layer on every with-layer run, only that it was available.

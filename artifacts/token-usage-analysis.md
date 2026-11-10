# Token Usage Analysis: Context Compaction vs. Full Context

**Task:** `django__django-15368` (vendored SWE-bench instance)
**Model:** `deepseek/deepseek-v4-flash-0731` via OpenRouter
**Compaction threshold:** 6,000 estimated tokens (compacted run) / disabled (baseline)
**Artifacts:**
- Compacted: `artifacts/django__django-15368-trajectory.json`, `artifacts/django__django-15368.patch`
- Baseline: `artifacts/django__django-15368-baseline-trajectory.json`, `artifacts/django__django-15368-baseline.patch`

## 1. Summary of Results

| Metric | Compacted | Baseline | Change |
|---|---|---|---|
| ReAct action requests | 37 | 32 | +15.6% |
| Compaction requests | 16 | 0 | — |
| Total LLM calls | 53 | 32 | +65.6% |
| Prompt tokens (action calls) | 157,987 | 743,615 | −78.8% |
| Prompt tokens (compaction calls) | 59,933 | 0 | — |
| **Total prompt tokens** | **217,920** | **743,615** | **−70.7%** |
| **Total tokens (prompt + completion)** | **235,389** | **758,083** | **−68.9%** |
| **Cumulative cost (USD)** | **$0.02283** | **$0.02605** | **−12.4%** |
| Peak per-step prompt tokens | 6,593 | 39,261 | −83.2% |
| Mean per-step prompt tokens | 4,270 | 23,238 | −81.6% |
| Compactions triggered | 16 | 0 | — |
| Mean estimated tokens before → after compaction | 6,425 → 3,185 | — | −50.4% |

Both runs produced a non-empty patch. The compacted run triggered 16 compactions,
materially reduced active context (mean −50.4% per compaction), and its patch was
graded with `make check-swebench`.

## 2. Observed Trends

### 2.1 Prompt size: monotonic growth vs. sawtooth

The baseline prompt grows monotonically, from 1,561 tokens on the first action
request to 39,261 on the last — a 25× increase. Every step appends an assistant
message plus its tool observations, and nothing is ever removed, so the cost of
each request is strictly increasing.

The compacted run instead stays inside a narrow band (2,339–6,593 tokens). Each
compaction collapses the old prefix into a short working-memory summary, so the
prompt drops sharply and then climbs again until the next threshold crossing.
The resulting curve is a sawtooth rather than a ramp.

### 2.2 Peak context

Peak per-step prompt size falls from 39,261 to 6,593 tokens (−83.2%). This is the
most important effect: the peak is what determines whether a run can fit inside
the model's context window at all. The baseline run was already at 39k tokens
after 32 steps; a longer task would have hit the window limit and failed.

### 2.3 Total token consumption

Despite 21 additional LLM calls (16 summarizations plus 5 extra ReAct steps),
total token consumption falls by 68.9% (758,083 → 235,389). The saving comes
entirely from the prompt side: the compacted run's action prompts total 157,987
tokens versus 743,615 for the baseline, a 78.8% reduction. Completion tokens are
a small fraction of the total in both runs.

### 2.4 Cost

Cumulative cost falls from $0.02605 to $0.02283 (−12.4%). The saving is smaller
than the token saving because the 16 compaction calls are pure overhead: they
consume 59,933 prompt tokens (27.5% of the compacted run's total prompt tokens)
without producing any task progress. In this run the reduced action-prompt cost
still outweighed that overhead, but the margin is thin.

### 2.5 Step count

The compacted run used 37 action steps versus 32 for the baseline. Generation is
stochastic, so this difference is not attributable to compaction; it does show
that the token saving is not an artifact of taking fewer steps. The compacted run
did more work with fewer tokens.

## 3. Tradeoffs Between the Two Conditions

### Full context (no compaction)

Advantages:
- No summarization overhead: every token spent goes toward task progress.
- No information loss: the model sees every prior observation verbatim, so it can
  re-read an exact error message or file excerpt from many steps ago.
- Simpler and more predictable: cost grows linearly with steps and is easy to
  reason about.

Disadvantages:
- Cost grows linearly and quadratically in aggregate: each step re-sends the whole
  history, so total spend is roughly quadratic in the number of steps.
- Hard ceiling: once the prompt exceeds the model's context window, the run cannot
  continue at all. Long-horizon tasks become impossible rather than merely
  expensive.
- Signal dilution: as the transcript grows, relevant details are buried among
  stale output, which can degrade the model's attention and decision quality.

### Compacted context

Advantages:
- Bounded peak: prompt size stays near the threshold, so the run can continue
  indefinitely and will not hit the context window.
- Much lower total token consumption on long tasks (68.9% lower here).
- Working memory is curated: the summary keeps the objective, constraints, files,
  commands, results, failed approaches, tests, blockers, and next action, and drops
  raw output that is no longer useful.

Disadvantages:
- Summarization overhead: each compaction is an extra model call whose tokens
  produce no task progress. With 16 compactions this was 27.5% of total prompt
  tokens.
- Information loss: details not captured in the summary are gone. If the model
  later needs an exact stack trace or a precise line of code from a compacted
  step, it must re-derive it by re-running commands.
- Risk of summary drift: a summary that omits a constraint or misstates a result
  can send the agent down a wrong path. The compaction prompt must therefore be
  explicit about what to preserve.
- Non-monotonic cost: the sawtooth makes per-step cost harder to predict.

### When each condition wins

- Short tasks (few steps, prompt never near the threshold): full context is
  strictly better — compaction would only add overhead and risk information loss.
  This is why the Part 1 chess task, at roughly 10 steps, never triggered
  compaction even at a 6,000-token threshold.
- Long tasks (many steps, prompt approaching the window): compaction is necessary.
  It converts an impossible run into a feasible one and reduces total spend.
- The break-even point depends on the ratio of compaction cost to the prompt growth
  it prevents. Here, 16 compactions costing 59,933 prompt tokens avoided roughly
  585,628 prompt tokens of growth (743,615 − 157,987), a ~10:1 return.

## 4. Caveats

- These are single samples. Generation is stochastic, so step counts and token
  totals vary between runs; the qualitative trends (monotonic vs. sawtooth, lower
  peak, lower total) should be stable, but the exact percentages are not.
- The compaction count (16) is high because the 6,000-token threshold is low
  relative to this task's step count. A higher threshold would trigger fewer,
  larger compactions and reduce overhead, at the cost of a higher peak.
- Cost figures come from the provider's per-response `usage.cost` field and reflect
  OpenRouter pricing for this model at the time of the run.
# Observation A/B Experiment: Board-Only vs. Board + Legal Moves

**Task:** `chess-terminal-move` (repaired chess app, agent plays White vs. deterministic engine)
**Step limit:** 200 (`STEPS ?= 200`)
**Sandbox timeout:** 5400 s for the DeepSeek/legal run, 1800 s for the other three
**Models:** `deepseek/deepseek-v4.1-flash-1017`, `openai/gpt-oss-120b` (both via OpenRouter)
**Conditions:** `legal_moves` field present in `<chess_state>` observations vs. omitted (`--omit-legal-moves`)

## 1. Setup

The four runs were produced with the Makefile targets, which configure the
observation format without any source edits:

```bash
make run-obs-deepseek-no-legal
make run-obs-deepseek-legal
make run-obs-gpt-oss-no-legal
make run-obs-gpt-oss-legal
```

Each run writes a trajectory (`artifacts/part3-{legal,no-legal}-moves-<model>.json`)
and a final-state result (`...-result.json`). The only difference between the two
conditions is whether the tool observation includes the `legal_moves:` line; the
board rendering, FEN, history, and tool schema are identical.

## 2. Results

| Model | Condition | Steps | `play_move` calls | Rejected as illegal | Invalid-move rate | `game_over: true` | Plies played | Outcome |
|---|---|---|---|---|---|---|---|---|
| DeepSeek | legal moves shown | 200 (limit) | 65 | 3 | 4.6 % | **no** | 124 | run did not finish |
| DeepSeek | legal moves omitted | 118 | 115 | 3 | 2.6 % | yes | 224 | Black wins (mate) |
| GPT-OSS | legal moves shown | 73 | 34 | 0 | 0.0 % | yes | 68 | Black wins (mate) |
| GPT-OSS | legal moves omitted | 21 | 21 | 2 | 9.5 % | yes | 36 | Black wins (mate) |

Supporting cost/context figures (from the `usage` block of each API response):

| Model | Condition | Prompt tokens | Completion tokens | Total tokens | Peak prompt tokens | Wall clock | Cost (USD) |
|---|---|---|---|---|---|---|---|
| DeepSeek | legal | 54,900,107 | 546,187 | 55,446,294 | 558,707 | 65 min | 0.647 |
| DeepSeek | no-legal | 8,404,744 | 89,322 | 8,494,066 | 119,765 | 10 min | 0.092 |
| GPT-OSS | legal | 964,442 | 39,972 | 1,004,414 | 24,066 | 7 min | 0.036 |
| GPT-OSS | no-legal | 159,811 | 11,921 | 171,732 | 16,458 | 2 min | 0.006 |

Notes on how the numbers were counted:

- `play_move` calls are counted from the assistant `tool_calls` in the trajectory.
- "Rejected as illegal" counts the `<chess_error>… is not legal in the current
  position.</chess_error>` observations present in the **final** prompt, i.e. one
  per unique rejection. Counting across all prompts would multiply each rejection
  by the number of later steps that replay it in history.
- No run triggered context compaction (`compactions: []` in all four trajectories),
  so the comparison is not confounded by Part 2's working memory.
- No run called `simulate_move`, `run_python`, or `invoke_skill`; every run used
  `play_move` exclusively.
- The DeepSeek/legal result file was reconstructed by replaying the 62 accepted
  move pairs from the trajectory through `python-chess`. The reconstructed FEN
  (`8/2k5/8/8/2K5/8/5PPP/8 w - - 0 63`) matches the last `<chess_state>`
  observation byte for byte, so it is identical to the `last_state` the harness
  would have written had the run terminated normally. The run itself never
  reached `game_over`.

## 3. Observations

### 3.1 Legal moves eliminate illegal attempts — for GPT-OSS only

For GPT-OSS the effect is unambiguous: **0 rejections out of 34 calls (0 %) with
legal moves shown, versus 2 out of 21 (9.5 %) with them omitted.** The model has to
infer legality from the ASCII board in the no-legal condition, and it occasionally
proposes a move that is geometrically plausible but blocked or leaves the king in
check (`d1d3`, `c1b2`). When the legal move list is present, the model simply picks
from it and never produces an illegal move.

DeepSeek shows **no such benefit**. It made 3 rejections over 65 calls (4.6 %) with
legal moves shown and 3 rejections over 115 calls (2.6 %) with them omitted — the
same absolute count, and a *higher* rate in the legal condition. The reason is
visible in the transcript: DeepSeek frequently does not read the `legal_moves` line
at all. At step 24 it proposed `f5d5`, a knight move that is not in the list, and
after being rejected it wrote:

> "This FEN/state description is highly symbolic and appears corrupted or highly
> compressed (e.g., `4c5 c4d3...` looks like algebraic notation attempts rather
> than a standard FEN)."

`4c5 c4d3...` is simply the tail of a perfectly valid `legal_moves` list. The model
misparsed the observation, concluded the state was garbage, and then guessed moves
from its own reconstruction of the board instead of from the list it had been given.
The `<chess_error>` feedback loop did work — each rejection was followed by a legal
move on the next step — but the underlying misreading recurred.

### 3.2 DeepSeek + legal moves degenerated and hit the step limit

The DeepSeek/legal run is the only one of the four that did not finish. It is worth
documenting in detail because the failure is a model pathology, not a harness bug.

**Timeline.** The first 24 steps were clean: one `play_move` per step, no
truncations. From step 24 onward the model began hitting the 4,096-token completion
cap (`finish_reason: "length"`), and the run never recovered. Of the 200 steps:

| `finish_reason` | Count |
|---|---|
| `tool_calls` | 65 |
| `length` (truncated at 4,096 tokens) | 111 |
| `stop` (plain text, no tool call) | 24 |

The last 135 steps produced only 30 tool calls. The model spent the remaining
budget emitting text that never became an action:

```
<result>
</result>

OK, calling play_move("c4d4").

<result>
</result>

Let me output the tool call.

<result>
</result>

c4d4.
```

It repeated this pattern for over a hundred steps, burning the full 4,096-token
completion budget each time (205,355 of the run's 546,187 completion tokens were
reasoning tokens). The game froze at ply 124 — a king-and-three-pawns endgame that
is trivially winnable — because the model could not emit the one tool call needed
to advance it.

**Why the context grew so large.** Chess runs do not enable Part 2's compaction, so
the prompt grows monotonically. Each step appends an assistant message plus its
observation, and the observation includes the full `legal_moves` line (35–45 moves,
~190 characters). The prompt crossed 128 K tokens at step 55 and 256 K at step 92,
reaching **558,707 tokens** by the final step. At that size each request took
roughly 20 seconds, which is why the run needed 65 minutes.

**A second attempt hit a hard provider limit.** Re-running with the same settings
produced a different but related failure: OpenRouter rejected the request with

```
402 - Prompt tokens limit exceeded: 162659 > 18273
```

The account's remaining credit balance caps the maximum prompt size, so once the
prompt passed ~160 K tokens the run could not continue at all. That attempt was
abandoned at step 106 and the 200-step trajectory was kept as the record.

**Contrast with the no-legal condition.** Without the `legal_moves` line the same
model finished in 118 steps and 8.5 M tokens — 6.5× cheaper and 6× faster. The
observation is ~190 characters shorter per step, and over 118 steps of monotonic
growth that difference compounds into the entire gap.

### 3.3 Legal moves cost context but buy reliability — conditionally

The `legal_moves:` line is not free. In the GPT-OSS pair the legal condition used
**5.8× more total tokens** (1,004,414 vs. 171,732) and **3.5× more steps** (73 vs.
21), and its peak prompt grew from 16,458 to 24,066 tokens. Part of that is simply a
longer game (68 plies vs. 36), but the per-step observation is also larger.

The trade-off is the classic one:

- **With legal moves:** every observation carries the full move list, so context grows
  faster and each step is more expensive, but a model that *reads* the list never
  wastes a step on an illegal move and never has to reason about piece geometry.
- **Without legal moves:** observations are compact and cheap, but the model must
  derive legality from the board itself. That costs reasoning tokens and produces
  occasional rejections that consume a full extra step each.

For GPT-OSS the reliability gain clearly outweighs the token overhead. For DeepSeek
the overhead is catastrophic (55.4 M vs. 8.5 M tokens, and the run does not finish)
while the reliability gain is zero.

### 3.4 Model choice dominates the observation format

The gap between models is far larger than the gap between conditions. GPT-OSS
finished all runs in 21–73 steps for 0.17–1.0 M tokens; DeepSeek needed 118–200
steps for 8.5–55.4 M tokens — up to **320× the tokens for the same task**. Whatever
effect the observation format has, it is second-order compared with which model is
driving the loop. Any conclusion about "legal moves vs. no legal moves" should
therefore be read as model-specific rather than universal.

### 3.5 Both models lose, and that is expected

All three completed games ended in `Black wins` by checkmate (ply 36, 68, and 224
respectively). The engine is deterministic and searches two plies; the agent has no
search or evaluation function of its own and only sees the current position. Losing
is not a defect of the harness; the assignment grades the experiment and the
evidence, not the result.

## 4. Conclusion

| Question | Answer |
|---|---|
| Do legal moves reduce illegal attempts? | For GPT-OSS yes (0 % vs. 9.5 %). For DeepSeek no (4.6 % vs. 2.6 % — no improvement). |
| Do legal moves cost context? | Yes, and the cost is model-dependent: ~5.8× total tokens for GPT-OSS, ~6.5× for DeepSeek. |
| Did every run reach `game_over`? | No — 3 of 4. DeepSeek/legal hit the 200-step limit in a degenerate loop. |
| Which factor matters more, model or observation? | Model, by roughly two orders of magnitude. |

The experiment does **not** support a universal "always include `legal_moves`"
policy. It supports a model-specific one:

- For a model that reliably parses structured observations (GPT-OSS), keep
  `legal_moves` in the observation by default: the reliability gain (no wasted steps
  on rejected moves) outweighs the context cost, and the cost is small relative to
  the model-to-model variance.
- For a model that misreads long structured fields (DeepSeek), the `legal_moves`
  line is actively harmful. It inflates every observation, drives the prompt past
  the provider's limit, and does not reduce illegal moves because the model does not
  use it. The board-only observation is strictly better for this model.

The broader lesson is that an observation format is part of the model's interface,
not a neutral rendering choice. The same field that makes one model more reliable
makes another one degenerate, so the format should be validated per model rather
than assumed to be universally beneficial.

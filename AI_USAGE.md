# AI Usage

## Tools used

| Tool | Role |
|---|---|
| GitHub Copilot Chat (VS Code) | Primary pair-programming assistant: explaining the spec, reviewing my code, diagnosing environment errors, and drafting report prose |
| `deepseek/deepseek-v4.1-flash-1017` via OpenRouter | The model the assignment's agent drives at runtime (not used to write the assignment) |
| `openai/gpt-oss-120b` via OpenRouter | Second model for the Part 3 observation A/B experiment |

## How I used GitHub Copilot

### 1. Understanding the assignment

- Translated `ASSIGNMENT.md` into Chinese (`assignment-cn.md`) so I could read the
  spec faster.
- Asked it to explain concepts I had no background in: the ReAct loop, the
  `system`/`user`/`assistant`/`tool` message roles and `tool_call_id` correlation,
  FEN and UCI chess notation, what a Modal sandbox actually is, and how context
  compaction works.

### 2. Environment setup and debugging

- Diagnosed `uv run modal setup` failing behind a local HTTP proxy: `modal` reads
  proxy environment variables but needs the optional `python-socks` package. Fix:
  `uv add 'modal[api-proxy-support]'`.
- Diagnosed `modal.exception.VersionError` (workspace image builder `2026.10` vs the
  pinned `modal 1.5.3`, which supports at most `2025.06`). Workaround:
  `MODAL_IMAGE_BUILDER_VERSION=2025.06`.
- Diagnosed a leftover `raise NotImplementedError` at the end of `Agent.run` that
  crashed the run after `send_message` had already succeeded.
- Diagnosed a chess run that failed because `CHESS_TIMEOUT=1800` expired before the
  200-step budget was exhausted.

### 3. Implementation guidance

For each TODO I asked for an explanation of *what* the code had to do and *why*,
then wrote the code myself. Copilot reviewed the result and pointed out defects
(indentation, wrong tool name in a dispatcher branch, a missing board refresh after
`run_python`). TODOs covered:

- 1.1.a `Agent.build_prompt` and `self.messages`
- 1.1.b `CodeAgent` system and task prompts
- 1.2 `Agent.run` ReAct loop
- 1.3 `CodeAgent.execute_tool_calls`
- 1.4 skill discovery and `invoke_skill`
- 2.1 `Agent.compact_context`
- 3.1.a `PLAY_MOVE_TOOL` schema
- 3.1.b `_play_move` and the `ChessAgent` dispatcher
- 3.3 `simulate_move` schema and `_simulate_move`
- 3.4 `run_python` and `_run_python`
- 3.5 `_invoke_skill`

### 4. Analysis and reports

- Computed step counts, tool-call counts, illegal-move rates, and token usage from
  the trajectory JSON files.
- Drafted `artifacts/token-usage-analysis.md` and
  `artifacts/observation-experiment.md`. I verified every number against the raw
  JSON before keeping it, and corrected several counts that had been inflated by
  history replay.

### 5. Reconstructing the missing DeepSeek/legal result file

The DeepSeek/legal run hit the 200-step limit and therefore never wrote
`artifacts/part3-legal-moves-deepseek-result.json` (the CLI writes the result only
after `agent.run()` returns). I reconstructed that file rather than leaving it
missing, and I want to be explicit about how:

- I extracted the 62 accepted `(human_move, engine_move)` pairs from the
  `<chess_state>` observations in the trajectory.
- I replayed them through `python-chess` to rebuild the position, the move history,
  and the legal-move list.
- The reconstructed FEN (`8/2k5/8/8/2K5/8/5PPP/8 w - - 0 63`) matches the last
  observation in the trajectory exactly, and the file has the same 12 keys in the
  same order as the other three result files.

This is a reconstruction, not a file the harness produced. It is documented as such
in `artifacts/observation-experiment.md` §2. The run itself never reached
`game_over`, and the report says so.

I also attempted a second DeepSeek/legal run with `CHESS_TIMEOUT=5400`. It failed at
step 106 with an OpenRouter `402` error (`Prompt tokens limit exceeded: 162659 >
18273`) because the account's remaining credit balance caps the maximum prompt size.
I kept the 200-step trajectory as the record and did not retry further.

## What I did not delegate

- I ran every experiment myself: `make run-code-agent`, `make check-part1`,
  `make run-swebench-agent`, `make check-swebench`, and the four `run-obs-*` targets.
- I read the resulting trajectories and confirmed the reported metrics.
- All submitted code under `src/assignment/agent/` was typed by me and is code I can
  explain.

## Note on the assignment's own LLM usage

The agent under construction calls an external LLM at runtime. That is part of the
assignment itself, not AI assistance for writing the assignment.
# 作业 1：构建一个 Agent Harness（智能体运行框架）

Agent harness（智能体运行框架）提供了让语言模型（一个生成"可能字符串"的模型）能够观察环境并在环境中行动的接口。构建 agent harness 最流行的框架之一是 [ReAct](https://arxiv.org/abs/2210.03629)，它把对应环境观察、推理/思维链（chain-of-thought）以及智能体动作的文本交错地放进给语言模型的提示词中。在本作业中，你将用 ReAct 框架构建一个 harness。

在 **Part 1** 中，你将实现基础 [`Agent`](./src/assignment/agent/base.py) 的 ReAct 循环，它会被实例化为一个 [`CodeAgent`](./src/assignment/agent/code_agent.py)，在终端中行动以解决软件问题。你的 ReAct 循环将是抽象的，可应用于多个领域，从而让你看到 agent harness 的通用结构。你将实现让编码智能体能够在终端环境中观察和行动的机制，并应用可复用的 agent skills（智能体技能）来完成任务。然后你会让这个编码智能体修复一个国际象棋游戏应用中的问题。

在 **Part 2** 中，你将研究你的编码智能体在解决更复杂的软件问题时如何使用上下文。你将实现一个简单的上下文压缩（context compaction）方法，来管理你的智能体使用了语言模型上下文窗口的多少部分。

在 **Part 3** 中，你将使用你构建的基础 `Agent`，把它实例化为一个 `ChessAgent`，在你用 `CodeAgent` 修复过的应用上下棋。你将实现这个智能体的工具规格（tool specifications），让语言模型能够与运行在应用中的、基于规则的机器人对弈（你可以观战！）。你还将探索 programmatic tool calling（程序化工具调用），它把程序的能力带给智能体动作，并能让你的智能体通过执行 Python 代码来实施更复杂的策略。

三个部分的关系如下：

```text
                SWE-Bench issue
                      |
                      v
buggy chess app -> CodeAgent -> fix.patch -> repaired chess server
                                              ^
                                              |
                                    ChessAgent tools
```

## 环境搭建（Setup）

安装 [uv](https://docs.astral.sh/uv/)，然后运行：
```bash
make setup
```
这会用 `uv` 建立一个 Python 环境，下载并安装相关依赖。如果被固定的 `chess_app` 源码（你的智能体将要处理的任务）缺失或处于错误的 commit，这一步会失败。

本作业会用到 [Modal](https://modal.com/)，一个用于运行代码的云平台。这个平台让你能够安全地在云机器上运行你的智能体生成的代码。你的智能体所处的环境会是一个远程 Modal sandbox（沙箱），并在其中运行执行智能体动作的代码。首先，注册一个 Modal 账号（如果你还没有的话），并按照发给你的说明获取 Modal 上的计算额度。然后运行
```bash
uv run modal setup
```
来登录并在你的环境中配置 Modal。

配置好 Modal 之后，运行
```bash
cp .env.example .env
```
来创建包含你的环境密钥的文件——主要是 LLM API 相关信息。如果你已选修本课程，你会收到如何获取某个 LLM 提供商额度的说明。按照说明生成 API key，并确保正确配置该服务的 base URL。

```dotenv
OPENAI_BASE_URL=<OpenAI-compatible base URL>
OPENAI_API_KEY=...
OPENAI_MODEL=deepseek/deepseek-v4-flash-0731
OPENAI_MAX_RETRIES=5
```

默认情况下，你会使用 DeepSeek-V4-Flash 模型，如上所示。在明确指示时，你应当使用另一个模型。如果额度允许，欢迎你探索同一提供商的其他模型，但我们希望本作业用这个模型完成。

我们把任何会消耗 API 额度（来自 Modal 或 LLM 提供商）的活动称为 _billable_（计费）。你会在整个作业中运行计费的评测。我们建议你在相关仪表盘上监控用量，以确保好好利用 API 额度。

在一次计费运行之前，先在不启动 sandbox、不生成 token 的情况下验证 submodule、Modal 认证和模型端点：
```bash
make doctor
```

_（可选）_ 如果你想测试所有 Modal 组件是否按预期运行，请运行
```bash
make test-modal
make test-chess-modal
```

一个通用小技巧：你可以用
```bash
modal container list
```
来检查是否有正在运行的计费 Modal sandbox。如果环境异常关闭，sandbox 可能被遗留下来继续运行并消耗额度。你可以用 `modal container stop <container ID>` 来停止一个没有被正确终止的 sandbox。

## 公开测试（Public tests）

`make test` 很快、离线、不计费。起始代码会故意让学生的 TODO 相关测试失败。把这些里程碑当作指引；如果加入了澄清性测试，确切的 pytest 数量可能会变化。

通过公开测试并不等于完全正确。私有测试还会覆盖失败时的清理、重复/格式错误的 skills、并行 chess 调用、传输错误、artifact 一致性、patch 重放，以及真实的 Modal 集成。

## 规则（Rules）

- 不要修改 `tests/`、`tasks/`、`chess_app/`。
- 不要改动已提供的日志/清理逻辑，也不要在子类中重复共享的 ReAct 循环。
- 不要为通过测试而硬编码某个智能体任务的预期解法。你的智能体应当为给定任务生成走法或 patch。
- **绝不要暴露、记录或提交 API key 之类的凭据。** 小心 `.env` 文件的内容。
- 在整个作业过程中，你会用到多个智能体以及这些智能体的多个版本。在任何时刻，只使用该智能体对应的那套工具。

## Part 1：构建编码智能体并修复国际象棋应用

共享的 `Agent` 必须实现一个常规的 ReAct 循环：构建请求、获得一个 assistant 动作、执行它的工具调用、加入相关联的观察结果，然后重复直到完成。

### 1. 构建提示词（Build the prompt）

给语言模型的提示词是一串消息，用于在交互的每一步查询语言模型。一条消息是一个字典对象。它至少包含 `role` 和 `content` 两个键，也可以带有额外信息。消息的 `content` 可以是字符串，也可以是包含推理 token 的结构化对象，或者（本作业不涉及的情况）图像。消息的 `role` 可以取几个值之一。

`system` 角色用于提供常驻指令——关于领域的指令、环境信息、要遵守的规则、跨任务可能有用的通用策略等。`user` 角色提供任务信息[^1]，必要时还提供解决任务的额外指引。`assistant` 角色的消息用于表示 LLM 的生成结果，`tool` 角色的消息表示工具调用的结果，作为对环境的观察。你的任务是组织这些消息的顺序。按惯例，开头恰好有一条 `system` 消息，在任何 assistant 消息之前先有一条 `user` 消息。由于 LLM 一次生成一个响应，一条 `assistant` 消息后面应当跟着 `tool` 消息（揭示工具调用的结果）或一条 `user` 消息。你可以在 [OpenAI API reference](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create) 以及 vLLM 文档中的这个[示例](https://docs.vllm.ai/en/v0.7.2/getting_started/examples/openai_chat_completion_client_with_tools.html)里找到这些消息结构的信息。

你需要实现 `Agent.build_prompt` 方法。给定 system prompt 和可通过智能体类属性访问的 task prompt，以及你可能添加的任何额外簿记信息，这个方法应当准备好给语言模型的输入。如你所见，我们提供了 `Agent.query_language_model` 方法，它直接使用这个方法的输出来查询语言模型 API。你的实现需要为这次查询提供正确的输入。`Agent.query_language_model` 方法会为语言模型 API 提供工具和推理参数，并返回一个包含所有相关信息的结构。它还会维护步数——即 API 被查询的次数。API 负责把提供的提示词和工具渲染成单个 token 序列，这不是你需要处理的。它还提供了额外的机制来记录你的请求以供评分，你不应修改它。

智能体的 LLM 客户端会对提供商的临时故障最多重试 `OPENAI_MAX_RETRIES` 次。

> **TODO(1.1.a)**
> 添加机制来维护智能体在采取动作和观察结果过程中的状态。构造构成语言模型提示词的消息序列。它应当包含常驻指令、任务规格、先前的交互（包括之前轮次的观察、推理和动作）。注意这个方法应当与领域无关，并以适用于任何继承它的领域特定智能体的方式构造提示词。

接下来，你应当为 `CodeAgent` 构造 system prompt 和 task prompt。system 消息 _必须_ 逐字包含下面这个块，使用环境暴露的值：
```text
<system_information>
{
  "machine": <machine>,
  "release": <release>,
  "system": <system>,
  "version": <version>
}
</system_information>
```

> **TODO(1.1.b)**
> 为 `CodeAgent` 构造 system prompt 和 task_prompt。它们应当能被 `Agent.build_prompt` 方法使用。

### 2. 运行 ReAct 循环（Run the ReAct loop）

实现 `Agent.run` 的主体。

> **TODO(1.2)**
> 运行 ReAct 循环。编排这一序列：提示语言模型产生推理和动作、提取模型产生的工具调用、执行工具调用以获得智能体下一步的观察结果。确保通过设置 `Agent.finished` 来识别智能体何时完成任务。如果智能体超过 `step_limit`，抛出 `StepLimitError`。

### 3. 执行编码工具（Execute coding tools）

实现 `CodeAgent.execute_tool_calls`。编码智能体支持两个工具：`execute` 和 `send_message`。你可以在[这里](./src/assignment/agent/tools.py)找到这些工具的定义。你需要实现一个执行这些工具的机制，并准备它们的输出以展示给语言模型。这些输出也是形如 `{"role": str, "tool_call_id": str, "content": str}` 的消息。每条消息是执行其中一个工具的观察结果，属于一个特殊角色 `tool`。[^2] 你应当使用 `Environment.execute` 方法来确保在正确的 Modal sandbox 上执行代码。你可以让可选参数保持当前默认值，但允许智能体在其工具调用中覆盖它们。

> **TODO(1.3)**
> 让 `execute` 和 `send_message` 工具对智能体可用。解析每个调用，执行已识别的工具，并为每个调用返回一条消息（一个智能体响应中可能有多个工具调用！）。格式错误的 JSON 和未知工具必须变成可恢复的观察结果并转达给智能体，而不是抛出异常。

### 4. 加载 skills（Load skills）

你可能以为我们已经准备好把智能体跑在一个软件问题上了，但还不行！`CodeAgent` 需要的最后一块知识是关于如何提交解法的说明。我们使用的具体协议是：一旦智能体解决了问题，它就把解法保存到一个名为 `patch.txt` 的文件中。这个文件会从环境中被提取出来用于评测。

为了教会智能体这个协议，我们会使用一个 skill。Skills 是通过专门化、可复用的工作流来扩展智能体能力的方式。[Agent Skills 协议](https://agentskills.io/home)定义了一个 skill 应当遵循的标准，以便能被多个智能体框架支持。`tasks/code-skills/submit-task` 定义了一个遵循该协议的、用于提交解法的初级 skill。虽然该协议还有更高级的特性可供探索，但本作业中你只需处理一个最小化的 skill。

你需要实现的核心特性是 _progressive disclosure_（渐进式披露）。为了让智能体能够使用许多 skill（每个都可能很复杂），skill 中的信息会以逐步增加的细节层级向智能体揭示，由智能体按需访问所需信息。在本作业中，你将实现一种简单形式的渐进式披露：在 _system prompt 中_ 给智能体提供所有可用 skill 的描述。你还会让智能体能够访问 `invoke_skill` 工具，智能体可以用一个 skill 名称调用它来查看完整的 skill。因此，当智能体查看完整的 `submit-task` skill 时，它就会知道如何提交修复以供评分。我们会检查 system prompt 中提到了 skill 的名称和描述。当智能体没有可用的 skill 时，提示词中任何部分都不应提到 `patch.txt`，也不应给智能体提交说明。

skill 文件在[本地](./tasks/code-skills/)可用，当智能体使用 skills 时（否则它被设为 `None`），`Agent.skills_path` 会指向这个位置。注意在本作业中，智能体只会使用一个 skill（`./tasks/code-skills/` 下的一个子文件夹），但原则上智能体可以有许多 skill 可用，这会让渐进式披露更加重要和有用。

> **TODO(1.4)**
> 校验 `skills_path`，在每个子目录中发现一个 `SKILL.md`，解析它的 YAML frontmatter（文件头部 `---` 标签之间的内容），并返回一个以 frontmatter 的 `name` 为键的映射。每个值必须包含一个简洁的 `metadata` 字符串（用于模型的 skill 目录）以及 skill 文件的完整 `content`（用于 `invoke_skill`）。对重复名称以及格式错误或缺失的 frontmatter，用清晰的 `ValueError` 拒绝。如果智能体有任何可用的 skill，就在提示词中把它们的描述/元数据提供给智能体。

例如，`SKILL.md` 的 `content` 为
```
---
name: hello-world
description: Write "hello, world" to the terminal
---

echo "hello, world"
```
而 `metadata` 为
```
name: hello-world
description: Write "hello, world" to the terminal
```

### 5. 运行并检查修复（Run and check the repair）

现在，让我们让智能体修复一个软件问题。

```bash
make run-code-agent
make check-part1
```

默认模型是 `deepseek/deepseek-v4-flash-0731`。智能体接收 `tasks/chess-terminal-move/problem_statement.md`，在 `/testbed` 内工作，并且必须复现、修复并验证该故障。一次运行会产生：

- `artifacts/fix.patch`
- `artifacts/part1-trajectory.json`

`make check-part1` 会把生成的 patch 应用到一个全新的 testbed 上，并运行公开回归测试以及 chess-app 测试套件。不要直接修改 `chess_app/` 中的目标。

完成 Part 1 后，你的解法应当通过与提示词构造、截断、步数限制、格式错误/未知工具以及 patch 提交相关的测试。

## Part 2：实现上下文压缩（Implement context compaction）

很长的 ReAct 记录会增加成本，并最终挤掉有用的上下文。随着智能体承担越来越复杂、时间跨度越来越长的任务，它们最终也会触及语言模型上下文窗口的极限。为了让智能体能够高效地处理运行时间更长的任务，我们希望只保留关于先前动作和观察的相关信息。这通过把上下文压缩成工作记忆（working memory）来实现。现在，你将在共享的 `Agent` 中实现一个由模型生成的工作记忆；不要使用提供商特定的压缩端点。

> **TODO(2.1)**
> 实现 `Agent.compact_context`。提示模型压缩上下文。压缩用的 system prompt 应当要求简洁、基于事实的工作记忆，并保留目标、约束、文件、命令、编辑、具体结果、失败的尝试、测试、阻塞项以及下一步动作。只总结一个较旧的前缀；逐字保留原始的 system/task 消息，并至少保留最新的完整 assistant 动作及其所有关联的 tool 观察结果。生成的摘要应当改变 `build_prompt` 的输出，并缩短提示词的长度。

**不要** 触碰智能体类的 `api_prompt` 和 `api_responses` 属性。它们用于簿记和评测。

> **TODO(2.2)**
> 在你的共享循环中，在每次新的动作请求之前调用 `maybe_compact_context()`。它已经会估算活跃 token 并处理阈值，还会为日志记录跟踪压缩事件。

用 6,000 token 的阈值运行 vendored 的 `django__django-15368` 任务：

```bash
COMPACT_THRESHOLD=6000 \
SWEBENCH_PATCH=artifacts/django__django-15368.patch \
SWEBENCH_TRAJECTORY=artifacts/django__django-15368-trajectory.json \
make run-swebench-agent INSTANCE=django__django-15368
make check-swebench INSTANCE=django__django-15368
```

设置 `COMPACT_THRESHOLD=0` 可以省略压缩标志，运行一个完整上下文的基线。当你想同时保留两次运行时，请使用不同的输出文件名，例如：

```bash
COMPACT_THRESHOLD=0 \
SWEBENCH_PATCH=artifacts/django__django-15368-baseline.patch \
SWEBENCH_TRAJECTORY=artifacts/django__django-15368-baseline-trajectory.json \
make run-swebench-agent INSTANCE=django__django-15368
```

提交的压缩运行必须至少触发一次压缩、显著减少活跃上下文，并产生一个能通过 `check-swebench` 的 patch。生成是随机的，所以它不必比每个基线样本使用更少的 ReAct 步数。

一旦你产生了压缩和不压缩两条轨迹，就比较两条轨迹的 token 使用情况。把你的观察写在 `artifacts/token-usage-analysis.md` 中，并为你观察到的趋势提供简要解释。压缩和不压缩两种条件下，上下文使用上的权衡是什么？

## Part 3：构建一个 `ChessAgent`

你的智能体在 Part 1 中已经修复了国际象棋应用的问题，所以现在你可以构建一个会下棋的智能体了。`ChessAgent` 复用 Part 1 和 Part 2 中完全相同的循环。它执白，而服务器上确定性的机器人执黑。服务器会在每一步合法的白方走法之后自动回应。

### 1. 实现 `play_move`

你首先要定义一个新工具，让智能体能够在应用中运行的对局中走棋。请遵循 [OpenAI function calling 指南](https://developers.openai.com/api/docs/guides/function-calling)来定义工具。

> **TODO(3.1.a)**
> 定义一个名为 `play_move` 的 OpenAI function-tool schema。它必须恰好接受一个名为 `move` 的必需字符串参数，说明走法使用 [UCI 记法](https://en.wikipedia.org/wiki/Universal_Chess_Interface)（例如 `e2e4` 和 `e7e8q`），并拒绝多余的参数。

然后，你将实现运行该工具的机制。[^3]

> **TODO(3.1.b)**
> 在 `chess_tools.py` 中实现 `_play_move`。解析参数，并向 `/api/move` POST `{"move": <uci move>}`。返回其序列化后的 JSON 对象。捕获工具抛出的任何错误，并返回一条位于 `<chess_error></chess_error>` 之间的错误消息，供智能体处理。要覆盖：格式错误的 JSON 参数、不是对象的参数、缺失或非字符串的 fen、非字符串的 move、服务器拒绝的局面或走法，以及传输失败。

你可以查看 `chess_app` 了解 API 是如何工作的。

用 `format_state` 方法格式化成功返回的状态，更新 `last_state`，并根据 `game_over` 设置 `finished`。用原始的 `tool_call_id` 关联观察结果。格式错误的 JSON、未知工具、非法走法和网络错误都会变成 `<chess_error>...</chess_error>` 观察结果。由于走棋后实时局面会变化，在一组并行调用中最多执行一步走法，并以可恢复的方式拒绝其余调用。

初始观察和成功走棋后的观察已经显示了棋盘、黑方的回应以及下一步的合法走法。不需要单独的读棋盘工具。

运行：

```bash
make run-chess-agent
```

这会应用你的 `fix.patch`，启动修复后的服务器，并保存：

- `artifacts/part3-trajectory.json`
- `artifacts/game-result.json`

打印出的 HTTPS URL 提供棋盘和 API。棋盘会在智能体下棋时轮询实时状态；它的按钮会刷新状态而不重置对局。`CHESS_TIMEOUT=1800` 控制 sandbox 的生命周期。

### 2. 运行观察 A/B 实验（Run the observation A/B experiment）

为了观察工具接口对智能体行为的影响，你将针对两个模型，比较"仅棋盘"观察与"棋盘加合法走法"观察。运行器无需修改源码即可配置这一点，并使用不同的文件名：

```bash
make run-obs-deepseek-no-legal
make run-obs-deepseek-legal
make run-obs-gpt-oss-no-legal
make run-obs-gpt-oss-legal
```

对四次运行中的每一次，记录 `play_move` 调用总数、因非法而被拒绝的调用数、非法走法率，以及是否达到 `game_over: true`。在 `artifacts/observation-experiment.md` 中写一份简短比较。评分依据是实验和证据，而不是某个特定结果或赢得对局。

### 3. 添加 `simulate_move`

为了让智能体具备规划更复杂策略的能力，你将赋予它模拟走法的能力。模拟允许智能体模拟走一步棋的效果，但不真正改变实际棋盘的状​​态。你将定义并注册 `SIMULATE_MOVE_TOOL`，实现 `_simulate_move`，并把它加入现有的 dispatcher。

> **TODO(3.3.a)**
> 像 `play_move` 工具那样定义 `simulate_move` 工具。

`simulate_move(fen, move=None)` 调用 `POST /api/simulate`。

只向 `simulate_move` 传入一个完整的六字段 [FEN](https://en.wikipedia.org/wiki/Forsyth%E2%80%93Edwards_Notation) 会返回该局面及其合法走法。传入 FEN 加 UCI 走法会返回恰好走一步（一个 ply）之后的局面，对任一方都适用。返回 JSON，以便 Python 可以使用 `fen`、`squares`、`turn`、`legal_moves` 以及终局结果字段。

> **TODO(3.3.b)**
> 在 `chess_tools.py` 中实现 `_simulate_move`。解析参数，用 FEN 和可选的 move 调用提供的 `/api/simulate` 端点，并返回其序列化后的 JSON。捕获工具抛出的任何错误，并返回一条位于 `<chess_error></chess_error>` 之间的错误消息，供智能体处理。要覆盖：格式错误的 JSON 参数、不是对象的参数、缺失或非字符串的 fen、非字符串的 move、服务器拒绝的局面或走法，以及传输失败。

你应当使用 `ChessAgent.chess_client` 来发送请求。

### 4. 添加 `run_python`

有了在棋盘上模拟走法的能力，智能体现在可以进行更复杂形式的规划。能够执行代码将让智能体更可靠地执行它想出的计划，你将通过 programmatic tool calling（程序化工具调用）来实现这一点。定义并注册 `RUN_PYTHON_TOOL`，实现 `_run_python`，并把它加入 dispatcher。模型提供 `run_python(code)`，而代码片段可以像普通同步 Python 函数一样调用 `simulate_move` 和 `play_move`。

> **TODO(3.4)**
> 解析参数，并在 sandbox 中运行代码，同时按名称提供已注册的工具。`/opt/assignment/sandbox_python.py` 是 `env` sandbox 上的一个脚本，它可以访问本文件中相同的工具定义。用它来运行模型作为 `run_python` 工具参数产生的代码。该脚本接受两个位置参数——`port` 和一个 base64 编码的代码字符串（以避免引号问题）。实现这个工具调用。
> 该脚本会打印一个 JSON 对象，包含运行代码得到的 `stdout`、`stderr` 和 `error`——原样返回那个字符串。非零返回码意味着 sandbox 本身失败了，而不是模型的代码失败。把 `exception_info` 或 `stderr` 作为 `<chess_error>` 报告。
> 如果存在类型不匹配或解析失败之类的问题，返回 `<chess_error>{message}</chess_error>`。

模型编写的代码绝不能在本地的智能体进程中运行。`_run_python` 通过 `env.execute` 把 base64 编码的代码发送给提供的 sandbox runner：

```text
python /opt/assignment/sandbox_python.py <port> <base64-code>
```

返回 runner 的 JSON 字符串，其中包含 `stdout`、`stderr` 和 `error`。非零的 sandbox 命令会变成 `<chess_error>`。代码片段抛出的 Python 异常是一次成功的 runner 调用，应当放在它的 `error` 字段中。每执行完一个代码片段后，重新读取实时棋盘，更新 `last_state` 和 `finished`，并把格式化后的状态追加到观察结果中；否则模型可能会重放一个代码片段已经提交过的走法。

用以下命令启用这些工具：

```bash
uv run assignment-play-chess --programmatic-tools
```

实现完这些之后，你的智能体应当能够产生一段选择走法的代码，并在对局中走出那一步。你可能仍会发现你的下棋智能体没有利用它可用的工具来走出好棋，而是经常直接使用 `play_move` 来行动。为了给它更多结构和策略，我们再次回到之前探索过的 skill 这个想法。

### 5. 加载并使用 chess skill（Load and use the chess skill）

虽然运行 Python 代码的能力给了智能体执行复杂计划的选择，但智能体可能没有这样做的倾向。为了给智能体一个可执行的具体策略，我们在 `tasks/chess-skills/select-move` 中提供了另一个 skill。为了让模型使用它，你将把 `CodeAgent` 的部分 skill 使用能力赋予 `ChessAgent`。由于工具执行机制略有不同，你必须在 `_invoke_skill(skills, arguments)` 中为 `ChessAgent` 重新实现 `invoke_skill` 工具的处理，只在加载了 skills 时注册 `INVOKE_SKILL_TOOL`，并返回指定名称的完整内容。

> **TODO(3.5)**
> 解析参数并返回指定名称 skill 的内容。如果存在类型不匹配或解析失败之类的问题，返回 `<chess_error>{message}</chess_error>`。

```bash
uv run assignment-play-chess \
  --programmatic-tools \
  --skills-path tasks/chess-skills \
  --patch artifacts/fix.patch \
  --trajectory artifacts/part3-python-skill-trajectory.json
```

轨迹必须展示 `invoke_skill`，然后是调用 `simulate_move` 进行搜索、并调用一次 `play_move` 来提交的 `run_python` 代码。读取 skill 后每回合直接调用一次 `play_move` 并不能证明这些工具协同工作。对局不必结束或获胜。

## 评分（Grading）

本作业满分 **100 分**。每一行独立评分；一次失败的随机模型运行不会抹掉无关的实现得分。

| Part | 评分标准 | 分值 | 证据 |
|---|---|---|---|
| 1 | 提示词构造以及有效的动作/观察历史 | 6 | 私有单元测试 |
| 1 | ReAct 生命周期、纯文本恢复、步数限制、清理、轨迹 | 6 | 私有单元测试 |
| 1 | 编码工具分发、可恢复错误、patch 提交 | 6 | 私有单元测试 |
| 1 | Chess patch 能应用并通过私有/回归测试 | 8 | 在全新 testbed 中重放 patch |
| 1 | Skill 发现与 `invoke_skill` 行为 | 4 | 私有测试 |
| 2 | 压缩触发与模型生成的摘要 | 6 | 私有测试与轨迹 |
| 2 | 原始指令和完整的近期工具步骤仍然有效 | 6 | 私有测试与轨迹 |
| 2 | 可审计的压缩显著减少活跃上下文 | 4 | 压缩事件与用量 |
| 2 | 完整上下文 vs. 压缩的 token 用量分析报告 | 4 | 报告 |
| 2 | SWE-bench patch 通过 FAIL_TO_PASS 和 PASS_TO_PASS | 8 | Patch 重放 |
| 3 | `play_move` schema 与注册 | 4 | 私有测试 |
| 3 | `play_move` 状态更新与可恢复错误 | 6 | 私有测试 |
| 3 | 基础 chess 轨迹达到终局状态 | 4 | 轨迹与结果 |
| 3 | 四次运行的观察 A/B 实验完整 | 4 | 四条轨迹、四个结果 |
| 3 | 观察 A/B 实验报告 | 4 | 报告 |
| 3 | `simulate_move` 无状态行为与错误 | 6 | 私有单元/集成测试 |
| 3 | `run_python` sandbox 执行、状态刷新、错误 | 6 | 带 sandbox 替身的私有测试 |
| 3 | Skill 轨迹结合 skill、程序化搜索和实时走棋 | 6 | 轨迹重放 |
| — | 完整、可解析、符合规则的提交 | 2 | 归档校验 |
| | **总计** | **100** | |

评分器会重放 patch 和提交的轨迹；它不会发起新的 LLM 调用。缺失或不一致的证据只会让受影响的那一行失分。教师测试和参考 patch 不包含在本仓库中。

## 提交（Submission）

提交一个 ZIP 归档，包含你在 `src/assignment/agent/` 下修改过的文件，以及以下 artifacts：

```text
artifacts/fix.patch
artifacts/part1-trajectory.json
artifacts/django__django-15368.patch
artifacts/django__django-15368-trajectory.json
artifacts/token-usage-analysis.md
artifacts/part3-trajectory.json
artifacts/game-result.json
artifacts/part3-no-legal-moves-deepseek.json
artifacts/part3-no-legal-moves-deepseek-result.json
artifacts/part3-legal-moves-deepseek.json
artifacts/part3-legal-moves-deepseek-result.json
artifacts/part3-no-legal-moves-gpt-oss.json
artifacts/part3-no-legal-moves-gpt-oss-result.json
artifacts/part3-legal-moves-gpt-oss.json
artifacts/part3-legal-moves-gpt-oss-result.json
artifacts/observation-experiment.md
artifacts/part3-python-skill-trajectory.json
```

只有在你修改了 `src/assignment/prompts.py` 时才一并包含它。**不要** 提交凭据、`.env`、任务文件、测试、submodule 内容或教师文件。你的 ZIP 应当包含 `src/` 和 `artifacts` 子文件夹，以及一个 `AI_USAGE.md` 文件。`AI_USAGE.md` 应当详细说明你在本作业中对任何 AI 技术的使用。列出你使用的所有工具，并清楚描述你如何使用每一个工具。如果你没有使用任何 AI 辅助，请在该文件中声明。我们不会给提交的 `AI_USAGE.md` 文件评分，但我们会通过一次测验（细节将另行通知）来检查你对所提交代码的理解。

[^1]: 在像这样的离线评测设置中，你通常通过把任务组织成一个来自用户的请求来指定任务。更多示例见这些[文档](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/chatgpt?tabs=python-key%2Cdotnet-secure%2Cjavascript-secure&pivots=programming-language-python)。

[^2]: 提供商重复出现的 `call_0` ID 是合法的：把每条工具观察结果匹配到同一个 assistant 动作中的调用，不要假设 ID 在整条轨迹中全局唯一。

[^3]: `_play_move` 和其他工具被隔离在 `chess_tools.py` 中，以便能够在远程 sandbox 中执行这些工具。请在这个代码结构内工作，以正确使用 Modal sandbox 来执行 chess 走法。

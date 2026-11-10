"""The Part 1 coding agent: fix a software issue and submit a git patch."""

from __future__ import annotations

import json
from typing import Any

from assignment.agent.base import (
    DEFAULT_COMPACTION_KEEP_RECENT_STEPS,
    DEFAULT_COMPACTION_MAX_TOKENS,
    Agent,
    format_tool_output,
)
from assignment.agent.tools import EXECUTE_TOOL, SEND_MESSAGE_TOOL
from assignment.env import Environment

class CodeAgent(Agent):
    """An agent that fixes a software issue and submits a git patch."""

    def __init__(
        self,
        task: str,
        environment: Environment,
        model: str | None = None,
        logs_save_path: str | None = None,
        step_limit: int = 100,
        skills_path: str | None = None,
        auto_stop_environment: bool = True,
        compact_threshold_tokens: int | None = None,
        compaction_keep_recent_steps: int = DEFAULT_COMPACTION_KEEP_RECENT_STEPS,
        compaction_max_tokens: int = DEFAULT_COMPACTION_MAX_TOKENS,
    ):
        super().__init__(
            environment=environment,
            model=model,
            logs_save_path=logs_save_path,
            step_limit=step_limit,
            skills_path=skills_path,
            auto_stop_environment=auto_stop_environment,
            compact_threshold_tokens=compact_threshold_tokens,
            compaction_keep_recent_steps=compaction_keep_recent_steps,
            compaction_max_tokens=compaction_max_tokens,
        )
        self.task = task
        self.submitted_patch = ""

        # TODO(Part 1.3): Make the `execute` and `send_message` tools available
        # to the agent.
        # 使用extend因为base可能已经包含了INVOKE_SKILLS 这样的技能
        self.tools.extend([EXECUTE_TOOL, SEND_MESSAGE_TOOL])
        # TODO(1.1.b): Construct the system prompt and task_prompt. These
        # should be usable by the `Agent.build_prompt` method.
        system_information = (
            "<system_information>\n"
            "{\n"
            f'  "machine": "{self.env.machine}",\n'
            f'  "release": "{self.env.release}",\n'
            f'  "system": "{self.env.system}",\n'
            f'  "version": "{self.env.version}"\n'
            "}\n"
            "</system_information>"
        )
        self.system_prompt = (
            "You are a coding agent working in a terminal environment.\n"
            "Fix the software issue by inspecting the repository, editing files, "
            "and running tests.\n\n"
            f"{system_information}\n\n"
            "Use the `execute` tool to run shell commands and `send_message` to "
            "report progress."
        )
        self.task_prompt = f"Fix the following issue:\n\n{self.task}"
        # TODO(1.4): If any skills are available to the agent, make their
        # descriptions/metadata available to the agent in the prompt.
        if self.skills:
            catalog = "\n".join(skill["metadata"] for skill in self.skills.values())
            # 注意是+=，而且只拼接 catlog(各个 skill 的 metadata)
            self.system_prompt += (
                "\n\nReusable skills are available. Call `invoke_skill` with a "
                "skill's name to load its instructions, and follow them in place "
                f"of your default approach.\n\n<skills>\n{catalog}\n</skills>\n"
            )

    def execute_tool_calls(
        self, tool_calls: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        """Execute ``execute`` and ``send_message`` calls in the code sandbox."""

        # TODO(Part 1.3): Parse each call, execute recognized tools, and return
        # one message per call (there may be multiple tool calls in one agent
        # response!). Malformed JSON and unknown tools must become recoverable
        # observations relayed to the agent instead of exceptions.
        
        observations: list[dict[str, str]] = []
        for call in tool_calls:
            # 一个 call 的样子是：
            # {
            #     "id": "call_1",
            #     "type": "function",
            #     "function": {
            #         "name": "execute",                              # ← 对应 schema 的 name
            #         "arguments": "{\"command\": \"ls -la\"}"        # ← 符合 parameters schema 的 JSON 字符串
            #     }
            # }
            call_id = call.get("id", "")
            function = call.get("function", {}) # function 指的是工具调用中的函数信息
            name = function.get("name", "")
            raw_arguments = function.get("arguments", "")

            # 参数需要是 JSON 字符串
            try:
                arguments = json.loads(raw_arguments)
            except (json.JSONDecodeError, TypeError):
                observations.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": f"Error: arguments were not valid JSON: {raw_arguments!r}",
                    }
                )
                continue

            # 参数需要是 JSON 对象
            if not isinstance(arguments, dict):
                observations.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": f"Error: arguments were not a JSON object: {raw_arguments!r}",
                    }
                )
                continue

            if name == "execute":
                try:
                    result = self.env.execute(**arguments)
                except TypeError as exc:
                    content = f"Error: invalid arguments for execute: {exc}"
                else:
                    content = format_tool_output(result)
            elif name == "send_message":
                self.submitted_patch = arguments.get("summary", "")
                self.finished = True
                content = "Message received."
            elif name == "invoke_skill": # 这个名字是工具名字
                skill_name = arguments.get("name","") # 技能名字是工具的参数
                skill = self.skills.get(skill_name) # 字典：这个skill的metadata和完整内容
                if skill is None:
                    content = f"Error: unknown skill {skill_name!r}."
                else:
                    content = skill["content"]
            else:
                content = f"Error: unknown tool: {name!r}"

            observations.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id, # 对应每一个call的id
                    "content": content,
                }
            )

        return observations
        

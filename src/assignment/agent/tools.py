"""Tool definitions exposed to the model, in the OpenAI tool-calling format."""

EXECUTE_TOOL = {
    "type": "function",
    "function": {
        "name": "execute",
        "description": (
            "Run a bash command and return its stdout, stderr, and exit code. "
            "A non-zero exit code is reported, not raised.\n"
            "\n"
            "Every command runs in a new subshell, so a `cd` or an export does not "
            "carry over to the next command. Use the `cwd` and `env` arguments "
            "instead. Files you write do persist.\n"
            "\n"
            "Commands are non-interactive and cannot prompt for input, so pass "
            "flags like `-y` where a command would otherwise ask for confirmation. "
            "Prefer commands that produce little output; when reading a file, use "
            "`head`, `tail`, or `sed -n '10,20p'` rather than printing all of it.\n"
            "\n"
            "Useful patterns:\n"
            "- Create a file: `cat <<'EOF' > newfile.py` ... `EOF`\n"
            "- Edit in place: `sed -i 's/old/new/g' filename.py` (drop the trailing "
            "`g` to replace only the first match; restrict to a line range with "
            "`sed -i '1,10s/old/new/g'`)\n"
            "- View numbered lines: `nl -ba filename.py | sed -n '10,20p'`"
        ),
        # The nested env object intentionally accepts arbitrary variable names,
        # which is incompatible with strict schemas on some providers.
        "strict": False,
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "anyOf": [
                        {
                            "type": "string",
                            "description": 'A shell command line, e.g. "ls -la | head".',
                        },
                        {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                'The command as an argv list, e.g. ["ls", "-la"]. '
                                "Use this with shell=false when arguments contain "
                                "characters the shell would interpret."
                            ),
                        },
                    ],
                    "description": "The command to run.",
                },
                "shell": {
                    "type": ["boolean", "null"],
                    "description": (
                        "Whether to run the command through a shell, which enables "
                        "pipes, redirection, and globbing. Defaults to true. Set to "
                        "false when passing an argv list."
                    ),
                },
                "cwd": {
                    "type": ["string", "null"],
                    "description": (
                        "Absolute path to run the command in. Defaults to the "
                        "sandbox's current working directory."
                    ),
                },
                "timeout": {
                    "type": ["number", "null"],
                    "description": (
                        "Seconds to allow the command to run before killing it. "
                        "Defaults to no timeout."
                    ),
                },
                "env": {
                    "type": ["object", "null"],
                    "additionalProperties": {"type": "string"},
                    "description": "Extra environment variables to set for this command.",
                },
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    },
}

SEND_MESSAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "send_message",
        "description": ("Send a message to the user."),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": ("Content of the message"),
                },
            },
            "required": ["summary"],
            "additionalProperties": False,
        },
    },
}

INVOKE_SKILL_TOOL = {
    "type": "function",
    "function": {
        "name": "invoke_skill",
        "description": (
            "Load a skill and return its instructions. A skill is a short guide "
            "for one kind of work, written ahead of time.\n"
            "\n"
            "Call this before starting work a skill covers, and follow what it "
            "says in place of your default approach."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "The skill's directory name, for example `hello-skill`."
                    ),
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
}

# TODO(3.1.a): Define an OpenAI function-tool schema named ``play_move``.
# It must accept exactly one required string argument named ``move``, explain
# that moves use UCI notation (for example e2e4), and reject extra arguments.
# 工具的schema
PLAY_MOVE_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "play_move",
        "description": (
            "Play one move as White in the live chess game. "
            "The move must use UCI notation: the origin square followed by the "
            "destination square, for example `e2e4` or `g1f3`. For a pawn "
            "promotion, append the piece letter in lowercase, for example "
            "`e7e8q` for a queen. The server replies automatically with Black's "
            "move and returns the resulting game state."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "move": {
                    "type": "string",
                    "description": "The move in UCI notation, e.g. e2e4 or e7e8q.",
                },
            },
            "required": ["move"],
            "additionalProperties": False,
        }
    },
}

# TODO(3.3): Define the `simulate_move` tool, like the `play_move` tool.
SIMULATE_MOVE_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "simulate_move",
        "description": (
            "Inspect a chess position or simulate exactly one move without "
            "changing the live game. This tool is stateless: it works on the "
            "FEN you supply, not on the current board.\n"
            "\n"
            "Pass only `fen` to get that position's board, turn, legal moves, "
            "and terminal status. Pass `fen` plus `move` to get the position "
            "after exactly one ply, for either color. Moves use UCI notation, "
            "for example `e2e4` or `e7e8q`.\n"
            "\n"
            "Use this to search ahead before committing a move with `play_move`."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "fen": {
                    "type": "string",
                    "description": (
                        "A complete six-field FEN describing the position to inspect, "
                        "e.g. `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1`."
                    ),
                },
                "move": {
                    "type": ["string", "null"],
                    "description": (
                        "Optional UCI move to apply to the FEN, e.g. `e2e4` or `e7e8q`. "
                        "Omit or pass null to only inspect the position and its legal moves."
                    ),
                },
            },
            "required": ["fen"],
            "additionalProperties": False,
        }
    },
}

# TODO()
RUN_PYTHON_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "run_python",
        "description": (
            "Execute Python code inside the sandbox, with the chess tools "
            "available as ordinary functions.\n"
            "\n"
            "The snippet can call:\n"
            "- `simulate_move(fen, move=None)` -> dict with `fen`, `squares`, "
            "`turn`, `legal_moves`, `game_over`, `winner`, `result`, "
            "`termination`. It does not change the live game.\n"
            "- `play_move(move)` -> dict with the new live state. This commits "
            "the move and the server replies as Black.\n"
            "\n"
            "Use `print()` to return information to yourself; only stdout, "
            "stderr, and any exception are reported back. Search with "
            "`simulate_move` first, then call `play_move` exactly once at the "
            "end to commit the chosen move."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python source to execute in the sandbox.",
                },
            },
            "required": ["code"],
            "additionalProperties": False,
        },
    },
}

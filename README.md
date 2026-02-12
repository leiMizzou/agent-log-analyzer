# 📋 agent-log-analyzer

**Parse and analyze AI agent session logs.**

Understand your agent's behavior: token patterns, tool usage, errors, costs.

```
$ agent-log-analyzer session.jsonl --model claude-sonnet-4

📋 agent-log-analyzer v0.1.0
───────────────────────────────────────────────────────
  File:       session.jsonl
  Model:      claude-sonnet-4
  Messages:   247 total
              (89 user, 94 assistant, 3 system, 61 tool)
  Tokens:     45,832 total (18,209 in / 27,623 out)
  Avg reply:  294 tokens (max: 2,104)
  Duration:   45.3 min (5.5 msg/min)
  Est. cost:  $0.4689

  Tool Usage (8 tools, 61 calls):
    ██████████████████████ exec (22)
    ███████████████ web_fetch (15)
    ████████████ browser (12)
    █████ Read (5)
    ███ Write (3)
    ... and 3 more (use --top-tools)
```

## Install

```bash
pip install agent-log-analyzer
```

Or download:
```bash
curl -O https://raw.githubusercontent.com/leiMizzou/agent-log-analyzer/main/agent_log.py
```

## Usage

```bash
# Analyze a session log
agent-log-analyzer session.jsonl

# With cost estimation
agent-log-analyzer session.jsonl --model claude-sonnet-4

# Show all tool usage
agent-log-analyzer session.jsonl --top-tools

# Show all errors
agent-log-analyzer session.jsonl --errors

# Analyze all sessions in a directory
agent-log-analyzer --dir ./sessions/

# JSON output
agent-log-analyzer session.jsonl --json
```

## Supported Formats

- **JSONL** — one message per line (OpenClaw, LangChain, etc.)
- **JSON** — array of messages or `{"messages": [...]}` format

## Cost Models

Built-in pricing for: GPT-4o, GPT-4o-mini, GPT-5, Claude Opus/Sonnet/Haiku 4, Gemini 2.5 Pro/Flash, DeepSeek V3/R1

## Features

- **Token analysis** — input/output/total breakdown
- **Tool usage** — frequency chart with visual bars
- **Error detection** — find and list errors
- **Cost estimation** — estimated spend per session
- **Duration tracking** — messages per minute
- **Multiple formats** — terminal, JSON

## License

MIT

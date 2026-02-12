#!/usr/bin/env python3
"""
📋 agent-log-analyzer — Parse and analyze AI agent session logs.

Extract insights from agent conversation logs: token usage patterns,
tool call frequency, error rates, response times, and cost trends.

Usage:
    python agent_log.py session.jsonl
    python agent_log.py --dir ./sessions/
    python agent_log.py session.jsonl --top-tools
    python agent_log.py session.jsonl --errors
    python agent_log.py session.jsonl --cost --model claude-sonnet-4

Zero dependencies. Python 3.8+.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

__version__ = "0.1.0"

# ─── Cost Database ──────────────────────────────────────────────────────────

COST_PER_1M = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-5": (10.00, 30.00),
    "claude-opus-4": (15.00, 75.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-haiku-4": (0.25, 1.25),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.15, 0.60),
    "deepseek-v3": (0.27, 1.10),
    "deepseek-r1": (0.55, 2.19),
}

# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class Message:
    role: str
    content: str
    timestamp: Optional[str] = None
    tokens: int = 0
    tool_calls: List[str] = field(default_factory=list)
    tool_results: List[Dict] = field(default_factory=list)
    is_error: bool = False
    latency_ms: float = 0

@dataclass
class SessionAnalysis:
    file: str
    total_messages: int
    user_messages: int
    assistant_messages: int
    system_messages: int
    tool_messages: int
    total_tokens: int
    input_tokens: int
    output_tokens: int
    tool_calls: Counter
    errors: List[Dict]
    avg_response_tokens: float
    max_response_tokens: int
    duration_minutes: float
    messages_per_minute: float
    unique_tools: int
    estimated_cost: Optional[float] = None
    model: str = ""

    def to_dict(self):
        d = {
            "file": self.file,
            "model": self.model,
            "total_messages": self.total_messages,
            "user_messages": self.user_messages,
            "assistant_messages": self.assistant_messages,
            "system_messages": self.system_messages,
            "tool_messages": self.tool_messages,
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tool_calls": dict(self.tool_calls.most_common()),
            "error_count": len(self.errors),
            "avg_response_tokens": round(self.avg_response_tokens, 1),
            "max_response_tokens": self.max_response_tokens,
            "duration_minutes": round(self.duration_minutes, 1),
            "unique_tools": self.unique_tools,
        }
        if self.estimated_cost is not None:
            d["estimated_cost_usd"] = round(self.estimated_cost, 4)
        return d

# ─── Log Parsers ────────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """Quick token estimate."""
    if not text:
        return 0
    cjk = len(re.findall(r'[\u4e00-\u9fff]', text))
    return max(1, int((len(text) - cjk) / 4 + cjk / 1.5))

def parse_jsonl(filepath: str) -> List[Message]:
    """Parse JSONL conversation log."""
    messages = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            msg = _parse_message(data)
            if msg:
                messages.append(msg)
    return messages

def parse_json(filepath: str) -> List[Message]:
    """Parse JSON conversation log."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
    
    msgs = data if isinstance(data, list) else data.get('messages', data.get('conversation', []))
    return [m for m in ((_parse_message(d) for d in msgs)) if m]

def _parse_message(data: dict) -> Optional[Message]:
    """Parse a single message from various formats."""
    role = data.get('role', data.get('type', ''))
    content = data.get('content', '')
    
    if isinstance(content, list):
        content = ' '.join(c.get('text', '') for c in content if isinstance(c, dict))
    elif not isinstance(content, str):
        content = str(content)
    
    tool_calls = []
    tc_data = data.get('tool_calls', data.get('function_call', []))
    if isinstance(tc_data, list):
        for tc in tc_data:
            name = tc.get('function', {}).get('name', '') or tc.get('name', '')
            if name:
                tool_calls.append(name)
    elif isinstance(tc_data, dict):
        name = tc_data.get('name', '')
        if name:
            tool_calls.append(name)
    
    is_error = bool(data.get('error')) or 'error' in content.lower()[:50]
    
    tokens = data.get('tokens', 0)
    if not tokens and content:
        tokens = estimate_tokens(content)
    
    timestamp = data.get('timestamp', data.get('created_at', data.get('time', '')))
    
    return Message(
        role=role,
        content=content,
        timestamp=str(timestamp) if timestamp else None,
        tokens=tokens,
        tool_calls=tool_calls,
        is_error=is_error,
    )

def load_messages(filepath: str) -> List[Message]:
    """Load messages from file."""
    if filepath.endswith('.jsonl'):
        return parse_jsonl(filepath)
    return parse_json(filepath)

# ─── Analysis ────────────────────────────────────────────────────────────────

def analyze_session(filepath: str, model: str = "") -> SessionAnalysis:
    """Analyze a session log file."""
    messages = load_messages(filepath)
    
    user_msgs = [m for m in messages if m.role in ('user', 'human')]
    asst_msgs = [m for m in messages if m.role in ('assistant', 'ai', 'bot')]
    sys_msgs = [m for m in messages if m.role == 'system']
    tool_msgs = [m for m in messages if m.role in ('tool', 'function')]
    
    # Token counts
    input_tokens = sum(m.tokens for m in user_msgs + sys_msgs)
    output_tokens = sum(m.tokens for m in asst_msgs)
    total_tokens = sum(m.tokens for m in messages)
    
    # Tool usage
    tool_counter = Counter()
    for m in messages:
        for tc in m.tool_calls:
            tool_counter[tc] += 1
    
    # Errors
    errors = []
    for m in messages:
        if m.is_error:
            errors.append({
                "role": m.role,
                "content": m.content[:200],
                "timestamp": m.timestamp,
            })
    
    # Response stats
    response_tokens = [m.tokens for m in asst_msgs if m.tokens > 0]
    avg_resp = sum(response_tokens) / len(response_tokens) if response_tokens else 0
    max_resp = max(response_tokens) if response_tokens else 0
    
    # Duration
    timestamps = [m.timestamp for m in messages if m.timestamp]
    duration = 0.0
    if len(timestamps) >= 2:
        try:
            first = _parse_ts(timestamps[0])
            last = _parse_ts(timestamps[-1])
            if first and last:
                duration = (last - first).total_seconds() / 60
        except:
            pass
    
    mpm = len(messages) / duration if duration > 0 else 0
    
    # Cost estimate
    cost = None
    if model:
        model_key = model.lower().replace(' ', '-')
        for key, (inp, out) in COST_PER_1M.items():
            if key in model_key or model_key in key:
                cost = input_tokens / 1_000_000 * inp + output_tokens / 1_000_000 * out
                break
    
    return SessionAnalysis(
        file=filepath,
        total_messages=len(messages),
        user_messages=len(user_msgs),
        assistant_messages=len(asst_msgs),
        system_messages=len(sys_msgs),
        tool_messages=len(tool_msgs),
        total_tokens=total_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_calls=tool_counter,
        errors=errors,
        avg_response_tokens=avg_resp,
        max_response_tokens=max_resp,
        duration_minutes=duration,
        messages_per_minute=mpm,
        unique_tools=len(tool_counter),
        estimated_cost=cost,
        model=model,
    )

def _parse_ts(ts_str: str) -> Optional[datetime]:
    """Try common timestamp formats."""
    for fmt in [
        "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f+00:00", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f",
    ]:
        try:
            return datetime.strptime(ts_str[:26], fmt[:26])
        except:
            continue
    return None

# ─── Output ──────────────────────────────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"

def format_terminal(analysis: SessionAnalysis, show_tools: bool = False,
                    show_errors: bool = False) -> str:
    lines = []
    lines.append(f"\n{BOLD}📋 agent-log-analyzer v{__version__}{RESET}")
    lines.append(f"{DIM}{'─' * 55}{RESET}")
    lines.append(f"  File:       {analysis.file}")
    if analysis.model:
        lines.append(f"  Model:      {analysis.model}")
    lines.append(f"  Messages:   {analysis.total_messages} total")
    lines.append(f"              ({analysis.user_messages} user, {analysis.assistant_messages} assistant, "
                 f"{analysis.system_messages} system, {analysis.tool_messages} tool)")
    lines.append(f"  Tokens:     {analysis.total_tokens:,} total ({analysis.input_tokens:,} in / {analysis.output_tokens:,} out)")
    lines.append(f"  Avg reply:  {analysis.avg_response_tokens:.0f} tokens (max: {analysis.max_response_tokens:,})")
    
    if analysis.duration_minutes > 0:
        lines.append(f"  Duration:   {analysis.duration_minutes:.1f} min ({analysis.messages_per_minute:.1f} msg/min)")
    
    if analysis.estimated_cost is not None:
        color = GREEN if analysis.estimated_cost < 0.10 else (YELLOW if analysis.estimated_cost < 1.00 else RED)
        lines.append(f"  Est. cost:  {color}${analysis.estimated_cost:.4f}{RESET}")
    
    # Tool usage
    if analysis.tool_calls:
        lines.append(f"\n  {BOLD}Tool Usage ({analysis.unique_tools} tools, {sum(analysis.tool_calls.values())} calls):{RESET}")
        for tool, count in analysis.tool_calls.most_common(15 if show_tools else 5):
            bar = "█" * min(count, 30)
            lines.append(f"    {CYAN}{bar}{RESET} {tool} ({count})")
        if not show_tools and len(analysis.tool_calls) > 5:
            lines.append(f"    {DIM}... and {len(analysis.tool_calls) - 5} more (use --top-tools){RESET}")
    
    # Errors
    if analysis.errors:
        err_color = RED if len(analysis.errors) > 5 else YELLOW
        lines.append(f"\n  {err_color}{BOLD}Errors: {len(analysis.errors)}{RESET}")
        show_n = len(analysis.errors) if show_errors else min(3, len(analysis.errors))
        for e in analysis.errors[:show_n]:
            lines.append(f"    {RED}✗{RESET} [{e['role']}] {e['content'][:80]}")
        if not show_errors and len(analysis.errors) > 3:
            lines.append(f"    {DIM}... and {len(analysis.errors) - 3} more (use --errors){RESET}")
    
    lines.append("")
    return '\n'.join(lines)

def format_json(analysis: SessionAnalysis) -> str:
    return json.dumps(analysis.to_dict(), indent=2)

# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="agent-log-analyzer",
        description="📋 Parse and analyze AI agent session logs",
    )
    parser.add_argument("target", nargs="?", help="Log file (.jsonl or .json)")
    parser.add_argument("--dir", "-d", help="Directory of log files")
    parser.add_argument("--model", "-m", help="Model name for cost estimation")
    parser.add_argument("--top-tools", action="store_true", help="Show all tool usage")
    parser.add_argument("--errors", action="store_true", help="Show all errors")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--cost", action="store_true", help="Show cost estimate")
    parser.add_argument("--version", "-v", action="version", version=f"agent-log-analyzer {__version__}")
    
    args = parser.parse_args()
    
    targets = []
    if args.target:
        targets.append(args.target)
    if args.dir:
        d = Path(args.dir)
        targets.extend(str(f) for f in d.glob("*.jsonl"))
        targets.extend(str(f) for f in d.glob("*.json"))
    
    if not targets:
        parser.print_help()
        sys.exit(1)
    
    for target in sorted(targets):
        analysis = analyze_session(target, args.model or "")
        if args.json:
            print(format_json(analysis))
        else:
            print(format_terminal(analysis, args.top_tools, args.errors))

if __name__ == "__main__":
    main()

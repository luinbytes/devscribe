"""AI integration using LiteLLM for model-agnostic summarization."""

import os
from typing import List, Optional
from datetime import datetime

from shellscribe.db import Command, Session, Config

# Try to import litellm, handle gracefully if not available
try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False


class AIError(Exception):
    """Exception raised for AI-related errors."""
    pass


def is_ai_available() -> bool:
    """Check if AI features are available and configured."""
    if not LITELLM_AVAILABLE:
        return False
    
    config = Config()
    if not config.ai_enabled:
        return False
    
    # Check for API keys based on model
    model = config.ai_model
    if model.startswith("zai/") or "zhipu" in model.lower():
        return bool(os.environ.get("ZHIPUAI_API_KEY"))
    elif model.startswith("openai/") or "gpt" in model.lower():
        return bool(os.environ.get("OPENAI_API_KEY"))
    elif model.startswith("anthropic/") or "claude" in model.lower():
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    
    # Generic check for other providers
    return True


def generate_summary(session: Session) -> str:
    """Generate an AI summary of a session's commands."""
    if not is_ai_available():
        raise AIError("AI features are not available. Check your configuration and API keys.")
    
    config = Config()
    commands = session.get_commands()
    
    if not commands:
        return "No commands recorded in this session."
    
    # Limit commands for context window
    max_cmds = config.get("max_commands_per_summary", 100)
    if len(commands) > max_cmds:
        commands = commands[-max_cmds:]
    
    # Format commands for the prompt
    cmd_text = format_commands_for_summary(commands)
    
    # Build the prompt
    prompt = f"""You are a helpful assistant that summarizes development sessions. 
Analyze the following shell commands from a coding session and provide a concise 5-bullet summary.

Focus on:
1. What was being built or worked on
2. Key technologies/frameworks used
3. Problems encountered (failed commands, errors)
4. Breakthroughs or successful operations
5. Overall progress made

Session Project: {session.project or 'Unknown'}
Session Started: {session.started_at.strftime('%Y-%m-%d %H:%M')}
Total Commands: {len(commands)}

Commands:
{cmd_text}

Provide exactly 5 bullet points summarizing this session. Be specific about what was done.
Format as a simple list with bullet points (• or -)."""

    try:
        model = config.ai_model
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise technical assistant that summarizes development sessions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500,
        )
        
        summary = response.choices[0].message.content.strip()
        
        # Save summary to session
        session.summary = summary
        session.save()
        
        return summary
        
    except Exception as e:
        raise AIError(f"Failed to generate summary: {str(e)}")


def format_commands_for_summary(commands: List[Command]) -> str:
    """Format commands into a readable string for AI summarization."""
    lines = []
    
    for cmd in commands:
        status = "✓" if cmd.is_success else f"✗({cmd.exit_code})"
        time_str = cmd.timestamp.strftime("%H:%M:%S")
        
        # Truncate very long commands
        cmd_text = cmd.command
        if len(cmd_text) > 200:
            cmd_text = cmd_text[:197] + "..."
        
        lines.append(f"[{time_str}] {status} {cmd_text}")
    
    return "\n".join(lines)


def generate_daily_summary(sessions: List[Session]) -> str:
    """Generate a summary of multiple sessions for a day."""
    if not is_ai_available():
        raise AIError("AI features are not available.")
    
    if not sessions:
        return "No sessions to summarize."
    
    # Collect all commands from all sessions
    all_commands = []
    for session in sessions:
        all_commands.extend(session.get_commands())
    
    if not all_commands:
        return "No commands recorded today."
    
    cmd_text = format_commands_for_summary(all_commands[-200:])  # Last 200 commands
    
    projects = list(set(s.project or "Unknown" for s in sessions))
    
    prompt = f"""Summarize today's development activity across these sessions.

Projects worked on: {', '.join(projects)}
Total sessions: {len(sessions)}
Total commands: {len(all_commands)}

Recent commands:
{cmd_text}

Provide a brief daily standup-style summary (3-4 bullet points) covering:
- What was accomplished
- Key challenges faced
- Technologies used
- Overall productivity assessment"""

    try:
        config = Config()
        response = litellm.completion(
            model=config.ai_model,
            messages=[
                {"role": "system", "content": "You are a concise technical assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=400,
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        raise AIError(f"Failed to generate daily summary: {str(e)}")


def explain_command(command: str, exit_code: int) -> str:
    """Get an explanation of why a command might have failed."""
    if not is_ai_available():
        return "AI explanation not available."
    
    if exit_code == 0:
        return "Command executed successfully."
    
    prompt = f"""A developer ran this command and it failed with exit code {exit_code}:

```
{command}
```

Briefly explain (2-3 sentences):
1. What this command was trying to do
2. Why it likely failed (common reasons)
3. How to fix it"""

    try:
        config = Config()
        response = litellm.completion(
            model=config.ai_model,
            messages=[
                {"role": "system", "content": "You are a helpful debugging assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300,
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception:
        return f"Could not generate explanation. Command failed with exit code {exit_code}."

"""Export functionality for ShellScribe sessions."""

from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path

from shellscribe.db import Session, Command, get_sessions


def export_to_markdown(
    sessions: List[Session],
    output_path: Optional[Path] = None,
    include_summary: bool = True,
) -> str:
    """Export sessions to markdown format."""
    lines = []
    
    # Header
    lines.append("# ShellScribe Development Log")
    lines.append(f"\n*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    
    if not sessions:
        lines.append("\n*No sessions to export.*\n")
        content = "\n".join(lines)
        if output_path:
            output_path.write_text(content)
        return content
    
    # Summary stats
    total_commands = sum(s.command_count for s in sessions)
    projects = list(set(s.project for s in sessions if s.project))
    
    lines.append("## Overview\n")
    lines.append(f"- **Sessions:** {len(sessions)}")
    lines.append(f"- **Commands:** {total_commands}")
    if projects:
        lines.append(f"- **Projects:** {', '.join(sorted(projects))}")
    lines.append("")
    
    # Sessions
    for session in reversed(sessions):  # Oldest first for chronological order
        lines.append(export_session_markdown(session, include_summary))
    
    content = "\n".join(lines)
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
    
    return content


def export_session_markdown(session: Session, include_summary: bool = True) -> str:
    """Export a single session to markdown."""
    lines = []
    
    # Session header
    start_str = session.started_at.strftime("%Y-%m-%d %H:%M")
    duration_str = ""
    if session.duration:
        mins = int(session.duration / 60)
        if mins < 60:
            duration_str = f" ({mins} min)"
        else:
            hours = mins // 60
            mins = mins % 60
            duration_str = f" ({hours}h {mins}min)"
    
    project_str = f" - **{session.project}**" if session.project else ""
    lines.append(f"\n## Session: {start_str}{duration_str}{project_str}\n")
    
    # AI Summary
    if include_summary and session.summary:
        lines.append("### AI Summary\n")
        lines.append(session.summary)
        lines.append("")
    
    # Commands table
    commands = session.get_commands()
    if commands:
        lines.append("### Commands\n")
        lines.append("| Time | Status | Command |")
        lines.append("|------|--------|---------|")
        
        for cmd in commands:
            time_str = cmd.timestamp.strftime("%H:%M:%S")
            status = "✓" if cmd.is_success else f"✗({cmd.exit_code})"
            # Escape pipe characters in command
            cmd_text = cmd.command.replace("|", "\\|").replace("\n", " ")
            if len(cmd_text) > 100:
                cmd_text = cmd_text[:97] + "..."
            lines.append(f"| {time_str} | {status} | `{cmd_text}` |")
        
        lines.append("")
        
        # Command statistics
        success_count = sum(1 for c in commands if c.is_success)
        error_count = len(commands) - success_count
        lines.append(f"*Total: {len(commands)} commands ({success_count} successful, {error_count} failed)*\n")
    
    return "\n".join(lines)


def export_day_summary(date: Optional[datetime] = None, output_path: Optional[Path] = None) -> str:
    """Export a single day's sessions."""
    if date is None:
        date = datetime.now()
    
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    
    sessions = list(
        Session.select()
        .where(
            (Session.started_at >= day_start) &
            (Session.started_at < day_end)
        )
        .order_by(Session.started_at)
    )
    
    return export_to_markdown(sessions, output_path)


def export_recent(days: int = 7, output_path: Optional[Path] = None) -> str:
    """Export recent sessions."""
    sessions = get_sessions(last_days=days)
    return export_to_markdown(sessions, output_path)


def export_project(project: str, output_path: Optional[Path] = None) -> str:
    """Export all sessions for a specific project."""
    sessions = get_sessions(project=project)
    return export_to_markdown(sessions, output_path)


def format_command_snippet(command: Command) -> str:
    """Format a single command as a code snippet."""
    status = "success" if command.is_success else f"exit code {command.exit_code}"
    return f"""```bash
# {command.timestamp.strftime('%Y-%m-%d %H:%M:%S')} [{status}]
# Working directory: {command.working_dir}
{command.command}
```"""


def export_commands_as_script(commands: List[Command], output_path: Optional[Path] = None) -> str:
    """Export successful commands as a reusable shell script."""
    lines = [
        "#!/bin/bash",
        "# ShellScribe Export - Successful Commands",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    
    successful = [c for c in commands if c.is_success]
    
    if not successful:
        lines.append("# No successful commands to export.")
    else:
        for cmd in successful:
            # Add comments for context
            lines.append(f"# {cmd.timestamp.strftime('%H:%M:%S')} - {cmd.working_dir}")
            lines.append(cmd.command)
            lines.append("")
    
    content = "\n".join(lines)
    
    if output_path:
        output_path.write_text(content)
        output_path.chmod(0o755)  # Make executable
    
    return content

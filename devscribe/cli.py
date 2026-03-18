"""CLI interface for DevScribe using Typer."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm

from devscribe import __version__
from devscribe.db import (
    Session,
    Command,
    Config,
    get_active_session,
    get_or_create_session,
    end_session,
    log_command,
    get_sessions,
    search_commands,
    detect_project,
)
from devscribe.ai import (
    generate_summary,
    is_ai_available,
    AIError,
    generate_daily_summary,
    explain_command,
)
from devscribe.export import (
    export_to_markdown,
    export_recent,
    export_project,
    export_commands_as_script,
)
from devscribe.hook import (
    install_hook,
    uninstall_hook,
    check_hook_status,
    get_hook_for_shell,
)

app = typer.Typer(
    name="devscribe",
    help="AI-powered terminal session logger - git log for your whole dev life",
    add_completion=True,
)
console = Console()


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"[bold blue]DevScribe[/bold blue] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """DevScribe - AI-powered terminal session logger."""
    pass


@app.command()
def start(
    project: Optional[str] = typer.Argument(
        None,
        help="Project name (auto-detected from git repo if not specified)",
    ),
):
    """Start a new development session."""
    active = get_active_session()
    if active:
        console.print(f"[yellow]Active session already exists[/yellow]")
        console.print(f"  Project: {active.project or 'Unknown'}")
        console.print(f"  Started: {active.started_at.strftime('%Y-%m-%d %H:%M')}")
        console.print(f"\nRun [bold]devscribe stop[/bold] to end it first.")
        raise typer.Exit(1)
    
    if project is None:
        project = detect_project(os.getcwd())
    
    session = get_or_create_session(project)
    
    console.print(Panel.fit(
        f"[bold green]Session started[/bold green]\n"
        f"Project: {session.project or 'Unknown'}\n"
        f"Time: {session.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
        title="DevScribe",
        border_style="blue",
    ))


@app.command()
def stop():
    """End the current session."""
    active = get_active_session()
    if not active:
        console.print("[yellow]No active session to stop.[/yellow]")
        raise typer.Exit(0)
    
    ended = end_session(active)
    
    duration = ""
    if ended.duration:
        mins = int(ended.duration / 60)
        if mins < 60:
            duration = f" ({mins} minutes)"
        else:
            hours = mins // 60
            mins = mins % 60
            duration = f" ({hours}h {mins}m)"
    
    console.print(Panel.fit(
        f"[bold green]Session ended[/bold green]\n"
        f"Project: {ended.project or 'Unknown'}\n"
        f"Duration: {duration}\n"
        f"Commands: {ended.command_count}",
        title="DevScribe",
        border_style="blue",
    ))


@app.command()
def log(
    command: str = typer.Argument(..., help="Command to log"),
    exit_code: int = typer.Argument(0, help="Exit code of the command"),
    working_dir: str = typer.Argument(".", help="Working directory"),
):
    """Log a command (typically called by the shell hook)."""
    # Resolve working directory
    wd = str(Path(working_dir).resolve())
    
    # Log the command
    cmd = log_command(command, exit_code, wd)
    
    # Silent output for hook usage - only print if something is wrong
    # This avoids cluttering the terminal


@app.command()
def status():
    """Show current session status."""
    active = get_active_session()
    
    if not active:
        console.print("[yellow]No active session[/yellow]")
        console.print("\nStart one with: [bold]devscribe start [project][/bold]")
        return
    
    duration = ""
    if active.started_at:
        elapsed = datetime.now() - active.started_at
        mins = int(elapsed.total_seconds() / 60)
        if mins < 60:
            duration = f"{mins} minutes"
        else:
            hours = mins // 60
            mins = mins % 60
            duration = f"{hours}h {mins}m"
    
    console.print(Panel.fit(
        f"[bold green]Active Session[/bold green]\n"
        f"Project: {active.project or 'Unknown'}\n"
        f"Started: {active.started_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Duration: {duration}\n"
        f"Commands: {active.command_count}",
        title="DevScribe Status",
        border_style="blue",
    ))
    
    # Show recent commands
    commands = active.get_commands()[-10:]  # Last 10
    if commands:
        console.print("\n[dim]Recent commands:[/dim]")
        for cmd in commands:
            status_icon = "✓" if cmd.is_success else f"✗({cmd.exit_code})"
            time_str = cmd.timestamp.strftime("%H:%M:%S")
            cmd_text = cmd.command[:60] + "..." if len(cmd.command) > 60 else cmd.command
            console.print(f"  [{time_str}] {status_icon} {cmd_text}")


@app.command()
def recap(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Specific session ID"),
    today: bool = typer.Option(False, "--today", "-t", help="Summarize all of today's sessions"),
    explain: Optional[int] = typer.Option(None, "--explain", "-e", help="Explain a failed command by ID"),
):
    """Generate an AI summary of your session."""
    # Check if AI is available
    if not is_ai_available():
        console.print("[yellow]AI features are not available.[/yellow]")
        console.print("Set your API key (e.g., ZHIPUAI_API_KEY) to enable AI summaries.")
        raise typer.Exit(1)
    
    # Explain a specific command
    if explain:
        try:
            cmd = Command.get_by_id(explain)
            explanation = explain_command(cmd.command, cmd.exit_code)
            console.print(Panel(explanation, title=f"Command Explanation", border_style="blue"))
            return
        except Command.DoesNotExist:
            console.print(f"[red]Command ID {explain} not found.[/red]")
            raise typer.Exit(1)
    
    # Get session to summarize
    session = None
    if session_id:
        try:
            session = Session.get_by_id(session_id)
        except Session.DoesNotExist:
            console.print(f"[red]Session ID {session_id} not found.[/red]")
            raise typer.Exit(1)
    else:
        session = get_active_session()
        if not session:
            # Get most recent session
            sessions = get_sessions(limit=1)
            if sessions:
                session = sessions[0]
    
    if today:
        # Summarize all of today's sessions
        sessions = get_sessions(today=True)
        if not sessions:
            console.print("[yellow]No sessions today.[/yellow]")
            return
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating daily summary...", total=None)
            try:
                summary = generate_daily_summary(sessions)
            except AIError as e:
                console.print(f"[red]Error: {e}[/red]")
                raise typer.Exit(1)
        
        console.print(Panel(
            summary,
            title=f"Daily Recap - {datetime.now().strftime('%Y-%m-%d')}",
            border_style="green",
        ))
        
    elif session:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating session summary...", total=None)
            try:
                summary = generate_summary(session)
            except AIError as e:
                console.print(f"[red]Error: {e}[/red]")
                raise typer.Exit(1)
        
        console.print(Panel(
            summary,
            title=f"Session Recap - {session.project or 'Unknown'}",
            border_style="green",
        ))
    else:
        console.print("[yellow]No session to summarize.[/yellow]")


@app.command("list")
def list_sessions(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project"),
    today: bool = typer.Option(False, "--today", "-t", help="Show only today's sessions"),
    last: Optional[int] = typer.Option(None, "--last", "-l", help="Show last N days"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number to show"),
    all_commands: bool = typer.Option(False, "--commands", "-c", help="Show all commands"),
):
    """List sessions and commands."""
    sessions = get_sessions(project=project, today=today, last_days=last, limit=limit)
    
    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return
    
    # Create table for sessions
    table = Table(title="Sessions" if not today else "Today's Sessions")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Started", style="cyan")
    table.add_column("Project", style="green")
    table.add_column("Commands", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Status", style="bold")
    
    for session in sessions:
        duration = ""
        if session.duration:
            mins = int(session.duration / 60)
            if mins < 60:
                duration = f"{mins}m"
            else:
                hours = mins // 60
                mins = mins % 60
                duration = f"{hours}h{mins}m"
        
        status = "[green]active[/green]" if session.is_active else "[dim]ended[/dim]"
        
        table.add_row(
            str(session.id),
            session.started_at.strftime("%m/%d %H:%M"),
            session.project or "-",
            str(session.command_count),
            duration or "-",
            status,
        )
    
    console.print(table)
    
    # Show commands if requested
    if all_commands and sessions:
        console.print("\n[bold]Recent Commands:[/bold]\n")
        for session in sessions[:3]:  # Limit to first 3 sessions
            commands = session.get_commands()
            if commands:
                console.print(f"[dim]Session {session.id} - {session.project or 'Unknown'}[/dim]")
                for cmd in commands:
                    status = "✓" if cmd.is_success else f"✗({cmd.exit_code})"
                    time_str = cmd.timestamp.strftime("%H:%M:%S")
                    cmd_text = cmd.command[:80] + "..." if len(cmd.command) > 80 else cmd.command
                    console.print(f"  [{time_str}] {status} {cmd_text}")
                console.print("")


@app.command("list-commands")
def list_commands(
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum commands to show"),
    failed: bool = typer.Option(False, "--failed", "-f", help="Show only failed commands"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project"),
):
    """List recent commands."""
    query = Command.select().join(Session)
    
    if failed:
        query = query.where(Command.exit_code != 0)
    
    if project:
        query = query.where(Session.project == project)
    
    query = query.order_by(Command.timestamp.desc()).limit(limit)
    
    commands = list(query)
    
    if not commands:
        console.print("[yellow]No commands found.[/yellow]")
        return
    
    table = Table(title="Recent Commands" if not failed else "Failed Commands")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Time", style="cyan")
    table.add_column("Status", width=8)
    table.add_column("Project", style="green")
    table.add_column("Command")
    
    for cmd in commands:
        status = "[green]✓[/green]" if cmd.is_success else f"[red]✗({cmd.exit_code})[/red]"
        time_str = cmd.timestamp.strftime("%m/%d %H:%M")
        cmd_text = cmd.command[:60] + "..." if len(cmd.command) > 60 else cmd.command
        
        table.add_row(
            str(cmd.id),
            time_str,
            status,
            cmd.session.project or "-",
            cmd_text,
        )
    
    console.print(table)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Use fzf for interactive search"),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum results"),
):
    """Search through command history."""
    commands = search_commands(query, limit)
    
    if not commands:
        console.print(f"[yellow]No commands matching '{query}'[/yellow]")
        return
    
    if interactive:
        # Try to use fzf
        try:
            import subprocess
            
            # Format commands for fzf
            lines = []
            for cmd in commands:
                time_str = cmd.timestamp.strftime("%Y-%m-%d %H:%M")
                status = "✓" if cmd.is_success else f"✗({cmd.exit_code})"
                lines.append(f"{time_str} {status} {cmd.command}")
            
            # Run fzf
            result = subprocess.run(
                ["fzf", "--height=40%", "--reverse", "--query", query],
                input="\n".join(lines),
                capture_output=True,
                text=True,
            )
            
            if result.returncode == 0 and result.stdout:
                console.print(f"\n[bold]Selected:[/bold] {result.stdout.strip()}")
            
        except FileNotFoundError:
            console.print("[yellow]fzf not found, showing results in table format.[/yellow]")
            interactive = False
        except Exception as e:
            console.print(f"[yellow]Could not use fzf: {e}[/yellow]")
            interactive = False
    
    if not interactive:
        table = Table(title=f"Search Results for '{query}'")
        table.add_column("Time", style="cyan")
        table.add_column("Status", width=8)
        table.add_column("Command")
        
        for cmd in commands:
            status = "[green]✓[/green]" if cmd.is_success else f"[red]✗({cmd.exit_code})[/red]"
            time_str = cmd.timestamp.strftime("%m/%d %H:%M")
            
            # Highlight matching part
            cmd_text = cmd.command
            if len(cmd_text) > 80:
                cmd_text = cmd_text[:77] + "..."
            
            table.add_row(time_str, status, cmd_text)
        
        console.print(table)


@app.command()
def export(
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    last: Optional[int] = typer.Option(None, "--last", "-l", help="Export last N days"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Export specific project"),
    today: bool = typer.Option(False, "--today", "-t", help="Export only today"),
    as_script: bool = typer.Option(False, "--script", "-s", help="Export as shell script"),
):
    """Export sessions to markdown or script."""
    # Determine what to export
    if today:
        sessions = get_sessions(today=True)
    elif last:
        sessions = get_sessions(last_days=last)
    elif project:
        sessions = get_sessions(project=project)
    else:
        # Default to last 7 days
        sessions = get_sessions(last_days=7)
    
    if not sessions:
        console.print("[yellow]No sessions to export.[/yellow]")
        return
    
    if as_script:
        # Export as shell script
        all_commands = []
        for session in sessions:
            all_commands.extend(session.get_commands())
        
        if output is None:
            output = Path(f"devscribe_export_{datetime.now().strftime('%Y%m%d')}.sh")
        
        content = export_commands_as_script(all_commands, output)
        console.print(f"[green]Exported {len(all_commands)} commands to {output}[/green]")
    else:
        # Export as markdown
        if output is None:
            output = Path(f"devscribe_export_{datetime.now().strftime('%Y%m%d')}.md")
        
        content = export_to_markdown(sessions, output)
        console.print(f"[green]Exported {len(sessions)} sessions to {output}[/green]")


@app.command()
def install(
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Show what would be done"),
):
    """Install the shell hook."""
    success, message = install_hook(dry_run=dry_run)
    
    if success:
        console.print(f"[green]{message}[/green]")
    else:
        console.print(f"[red]{message}[/red]")
        raise typer.Exit(1)


@app.command()
def uninstall():
    """Remove the shell hook."""
    success, message = uninstall_hook()
    
    if success:
        console.print(f"[green]{message}[/green]")
    else:
        console.print(f"[yellow]{message}[/yellow]")


@app.command()
def config(
    key: Optional[str] = typer.Argument(None, help="Config key to get/set"),
    value: Optional[str] = typer.Argument(None, help="Value to set"),
    list_all: bool = typer.Option(False, "--list", "-l", help="List all config values"),
):
    """View or modify configuration."""
    cfg = Config()
    
    if list_all:
        console.print("[bold]Current Configuration:[/bold]\n")
        for k, v in cfg._config.items():
            console.print(f"  {k}: [cyan]{v}[/cyan]")
        return
    
    if key is None:
        console.print("Use [bold]devscribe config KEY VALUE[/bold] to set a value")
        console.print("Use [bold]devscribe config --list[/bold] to see all values")
        return
    
    if value is None:
        # Get value
        current = cfg.get(key)
        if current is not None:
            console.print(f"{key}: [cyan]{current}[/cyan]")
        else:
            console.print(f"[yellow]Key '{key}' not found[/yellow]")
    else:
        # Set value
        # Handle boolean and integer values
        if value.lower() in ("true", "yes", "1"):
            value = True
        elif value.lower() in ("false", "no", "0"):
            value = False
        elif value.isdigit():
            value = int(value)
        
        cfg.set(key, value)
        console.print(f"[green]Set {key} = {value}[/green]")


@app.command()
def projects():
    """List all projects."""
    query = Session.select(Session.project).distinct().where(Session.project.is_null(False))
    projects = [s.project for s in query]
    
    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        return
    
    console.print("[bold]Projects:[/bold]\n")
    for project in sorted(projects):
        # Get session count
        count = Session.select().where(Session.project == project).count()
        console.print(f"  {project} [dim]({count} sessions)[/dim]")


@app.command()
def cleanup(
    days: int = typer.Option(30, "--days", "-d", help="Delete sessions older than N days"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted"),
):
    """Clean up old sessions."""
    from datetime import timedelta
    
    cutoff = datetime.now() - timedelta(days=days)
    
    old_sessions = Session.select().where(Session.started_at < cutoff)
    count = old_sessions.count()
    
    if count == 0:
        console.print("[green]No old sessions to clean up.[/green]")
        return
    
    if dry_run:
        console.print(f"[yellow]Would delete {count} sessions older than {days} days[/yellow]")
        return
    
    if Confirm.ask(f"Delete {count} sessions older than {days} days?"):
        deleted = Session.delete().where(Session.started_at < cutoff).execute()
        console.print(f"[green]Deleted {deleted} old sessions.[/green]")


def main_cli():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main_cli()

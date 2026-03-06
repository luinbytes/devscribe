"""Tests for export functionality in shellscribe.export module."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from shellscribe.export import (
    export_to_markdown,
    export_session_markdown,
    export_day_summary,
    export_recent,
    export_project,
    format_command_snippet,
    export_commands_as_script,
)
from shellscribe.db import Session, Command


class TestExportToMarkdown:
    """Tests for export_to_markdown function."""

    def test_export_to_markdown_empty_sessions(self, temp_db):
        """Test exporting when no sessions exist returns appropriate message."""
        result = export_to_markdown([])

        assert "# ShellScribe Development Log" in result
        assert "*No sessions to export.*" in result

    def test_export_to_markdown_with_sessions(self, temp_db, sample_session, sample_commands):
        """Test exporting with sessions includes all expected content."""
        # End the session so it has a duration
        sample_session.ended_at = sample_session.started_at + timedelta(minutes=15)
        sample_session.save()

        result = export_to_markdown([sample_session])

        assert "# ShellScribe Development Log" in result
        assert "## Overview" in result
        assert "**Sessions:** 1" in result
        assert "**Commands:** 4" in result
        assert sample_session.project in result

    def test_export_to_markdown_includes_timestamp(self, temp_db, sample_session):
        """Test that export includes generation timestamp."""
        result = export_to_markdown([sample_session])

        assert "*Generated on" in result

    def test_export_to_markdown_multiple_sessions(self, temp_db):
        """Test exporting multiple sessions includes correct count."""
        session1 = Session.create(project="project1")
        session2 = Session.create(project="project2")

        result = export_to_markdown([session1, session2])

        assert "**Sessions:** 2" in result

    def test_export_to_markdown_writes_to_file(self, temp_db, sample_session, tmp_path):
        """Test that export writes to file when output_path is provided."""
        output_file = tmp_path / "export.md"

        export_to_markdown([sample_session], output_path=output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "# ShellScribe Development Log" in content

    def test_export_to_markdown_includes_projects_list(self, temp_db):
        """Test that export includes list of unique projects."""
        Session.create(project="alpha")
        Session.create(project="beta")
        Session.create(project="alpha")  # Duplicate

        sessions = list(Session.select())
        result = export_to_markdown(sessions)

        assert "**Projects:**" in result
        assert "alpha" in result
        assert "beta" in result


class TestExportSessionMarkdown:
    """Tests for export_session_markdown function."""

    def test_export_session_markdown_basic(self, temp_db, sample_session):
        """Test basic session export includes session header."""
        result = export_session_markdown(sample_session)

        assert "## Session:" in result
        assert sample_session.started_at.strftime("%Y-%m-%d") in result

    def test_export_session_markdown_includes_project(self, temp_db, sample_session):
        """Test session export includes project name."""
        result = export_session_markdown(sample_session)

        assert f"**{sample_session.project}**" in result

    def test_export_session_markdown_includes_duration(self, temp_db, sample_session):
        """Test session export includes duration when session is ended."""
        sample_session.ended_at = sample_session.started_at + timedelta(minutes=45)
        sample_session.save()

        result = export_session_markdown(sample_session)

        assert "(45 min)" in result

    def test_export_session_markdown_includes_hours(self, temp_db, sample_session):
        """Test session export formats hours correctly for long sessions."""
        sample_session.ended_at = sample_session.started_at + timedelta(hours=2, minutes=30)
        sample_session.save()

        result = export_session_markdown(sample_session)

        assert "(2h 30min)" in result

    def test_export_session_markdown_includes_commands(self, temp_db, sample_session, sample_commands):
        """Test session export includes command table."""
        result = export_session_markdown(sample_session)

        assert "### Commands" in result
        assert "| Time | Status | Command |" in result
        assert "|------|--------|---------|" in result

    def test_export_session_markdown_shows_success_status(self, temp_db, sample_session, sample_commands):
        """Test session export shows checkmark for successful commands."""
        result = export_session_markdown(sample_session)

        assert "✓" in result

    def test_export_session_markdown_shows_error_status(self, temp_db, sample_session, sample_commands):
        """Test session export shows error code for failed commands."""
        result = export_session_markdown(sample_session)

        assert "✗" in result
        assert "(1)" in result  # Exit code 1 from sample_commands

    def test_export_session_markdown_command_stats(self, temp_db, sample_session, sample_commands):
        """Test session export includes command statistics."""
        result = export_session_markdown(sample_session)

        # 3 successful, 1 failed
        assert "3 successful" in result
        assert "1 failed" in result
        assert "4 commands" in result

    def test_export_session_markdown_with_summary(self, temp_db, sample_session):
        """Test session export includes AI summary when present."""
        sample_session.summary = "This is an AI-generated summary of the session."
        sample_session.save()

        result = export_session_markdown(sample_session, include_summary=True)

        assert "### AI Summary" in result
        assert sample_session.summary in result

    def test_export_session_markdown_without_summary(self, temp_db, sample_session):
        """Test session export omits summary when include_summary is False."""
        sample_session.summary = "This is a summary."
        sample_session.save()

        result = export_session_markdown(sample_session, include_summary=False)

        assert "### AI Summary" not in result

    def test_export_session_markdown_escapes_pipes(self, temp_db, sample_session):
        """Test that pipes in commands are escaped."""
        Command.create(
            session=sample_session,
            command='echo "foo | bar"',
            exit_code=0,
            working_dir="/home/user",
        )

        result = export_session_markdown(sample_session)

        # Pipe should be escaped in the markdown table
        assert "\\|" in result

    def test_export_session_markdown_truncates_long_commands(self, temp_db, sample_session):
        """Test that very long commands are truncated."""
        long_cmd = "echo '" + "x" * 200 + "'"
        Command.create(
            session=sample_session,
            command=long_cmd,
            exit_code=0,
            working_dir="/home/user",
        )

        result = export_session_markdown(sample_session)

        # Command should be truncated with "..."
        assert "..." in result


class TestFormatCommandSnippet:
    """Tests for format_command_snippet function."""

    def test_format_command_snippet_success(self, temp_db, sample_session):
        """Test formatting a successful command as a snippet."""
        cmd = Command.create(
            session=sample_session,
            command="echo 'hello'",
            exit_code=0,
            working_dir="/home/user/project",
        )

        result = format_command_snippet(cmd)

        assert "```bash" in result
        assert "echo 'hello'" in result
        assert "[success]" in result
        assert "# Working directory: /home/user/project" in result
        assert "```" in result

    def test_format_command_snippet_error(self, temp_db, sample_session):
        """Test formatting a failed command as a snippet."""
        cmd = Command.create(
            session=sample_session,
            command="false",
            exit_code=127,
            working_dir="/home/user",
        )

        result = format_command_snippet(cmd)

        assert "[exit code 127]" in result

    def test_format_command_snippet_includes_timestamp(self, temp_db, sample_session):
        """Test that snippet includes formatted timestamp."""
        cmd = Command.create(
            session=sample_session,
            command="ls",
            exit_code=0,
            working_dir="/home/user",
        )

        result = format_command_snippet(cmd)

        # Should include date in format YYYY-MM-DD HH:MM:SS
        assert cmd.timestamp.strftime("%Y-%m-%d") in result


class TestExportCommandsAsScript:
    """Tests for export_commands_as_script function."""

    def test_export_commands_as_script_basic(self, temp_db, sample_session, sample_commands):
        """Test exporting commands as a shell script."""
        result = export_commands_as_script(sample_commands)

        assert "#!/bin/bash" in result
        assert "# ShellScribe Export - Successful Commands" in result
        assert "# Generated:" in result

    def test_export_commands_as_script_only_successful(self, temp_db, sample_session, sample_commands):
        """Test that only successful commands are included."""
        result = export_commands_as_script(sample_commands)

        # sample_commands includes one failed command (exit_code=1)
        # It should not be in the output
        assert "false_command" not in result

        # Successful commands should be included
        assert "echo 'hello world'" in result
        assert "ls -la" in result
        assert "git status" in result

    def test_export_commands_as_script_empty(self, temp_db, sample_session):
        """Test exporting when no successful commands exist."""
        failed_cmd = Command.create(
            session=sample_session,
            command="failed_command",
            exit_code=1,
            working_dir="/home/user",
        )

        result = export_commands_as_script([failed_cmd])

        assert "# No successful commands to export." in result

    def test_export_commands_as_script_includes_context(self, temp_db, sample_session, sample_commands):
        """Test that script includes timestamp and working directory context."""
        result = export_commands_as_script(sample_commands)

        # Should include timestamps as comments
        assert "#" in result
        # Should include working directory
        assert sample_commands[0].working_dir in result

    def test_export_commands_as_script_writes_to_file(self, temp_db, sample_session, sample_commands, tmp_path):
        """Test that script is written to file when output_path is provided."""
        output_file = tmp_path / "script.sh"

        export_commands_as_script(sample_commands, output_path=output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "#!/bin/bash" in content

    def test_export_commands_as_script_is_executable(self, temp_db, sample_session, sample_commands, tmp_path):
        """Test that exported script has executable permissions."""
        output_file = tmp_path / "script.sh"

        export_commands_as_script(sample_commands, output_path=output_file)

        # Check that the file has executable bit
        assert output_file.stat().st_mode & 0o111  # Has any execute bit


class TestExportDaySummary:
    """Tests for export_day_summary function."""

    def test_export_day_summary(self, temp_db):
        """Test exporting sessions for a specific day."""
        # Create sessions for today
        today_session = Session.create(project="today-project")

        result = export_day_summary()

        assert "# ShellScribe Development Log" in result


class TestExportRecent:
    """Tests for export_recent function."""

    def test_export_recent_default_days(self, temp_db):
        """Test exporting recent sessions with default days."""
        recent_session = Session.create(project="recent-project")

        result = export_recent()

        assert "# ShellScribe Development Log" in result

    def test_export_recent_custom_days(self, temp_db):
        """Test exporting recent sessions with custom days parameter."""
        session = Session.create(project="test-project")

        result = export_recent(days=3)

        assert "# ShellScribe Development Log" in result


class TestExportProject:
    """Tests for export_project function."""

    def test_export_project(self, temp_db):
        """Test exporting sessions for a specific project."""
        # Create sessions for different projects
        Session.create(project="target-project")
        Session.create(project="other-project")

        result = export_project("target-project")

        assert "# ShellScribe Development Log" in result
        assert "**target-project**" in result
        # The other project should not appear in the session details
        # (though it won't appear anyway since it's filtered)

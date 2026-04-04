"""Tests for database operations in devscribe.db module."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from devscribe.db import (
    Session,
    Command,
    Config,
    get_active_session,
    get_or_create_session,
    end_session,
    log_command,
    detect_project,
    get_sessions,
    search_commands,
)


class TestSessionModel:
    """Tests for Session model operations."""

    def test_session_create(self, temp_db):
        """Test that a Session can be created with default values."""
        session = Session.create()

        assert session.id is not None
        assert session.started_at is not None
        assert session.ended_at is None
        assert session.project is None
        assert session.summary is None
        assert session.is_active is True

    def test_session_create_with_project(self, temp_db):
        """Test that a Session can be created with a project name."""
        session = Session.create(project="my-awesome-project")

        assert session.project == "my-awesome-project"
        assert session.is_active is True

    def test_session_duration(self, temp_db):
        """Test the session duration property calculation."""
        session = Session.create()
        session.ended_at = session.started_at + timedelta(minutes=30)
        session.save()

        assert session.duration is not None
        assert session.duration == 1800  # 30 minutes in seconds

    def test_session_duration_none_when_active(self, temp_db):
        """Test that duration is None for active sessions."""
        session = Session.create()

        assert session.duration is None

    def test_session_command_count(self, temp_db, sample_session, sample_commands):
        """Test the command_count property returns correct count."""
        assert sample_session.command_count == len(sample_commands)

    def test_session_get_commands(self, temp_db, sample_session, sample_commands):
        """Test that get_commands returns all session commands in order."""
        commands = sample_session.get_commands()

        assert len(commands) == len(sample_commands)
        # Commands should be ordered by timestamp
        for i in range(len(commands) - 1):
            assert commands[i].timestamp <= commands[i + 1].timestamp


class TestCommandModel:
    """Tests for Command model operations."""

    def test_command_create(self, temp_db, sample_session):
        """Test that a Command can be created with all fields."""
        cmd = Command.create(
            session=sample_session,
            command="echo 'test'",
            exit_code=0,
            working_dir="/home/user",
        )

        assert cmd.id is not None
        assert cmd.session.id == sample_session.id
        assert cmd.command == "echo 'test'"
        assert cmd.exit_code == 0
        assert cmd.timestamp is not None
        assert cmd.working_dir == "/home/user"

    def test_command_is_success(self, temp_db, sample_session):
        """Test the is_success property for successful commands."""
        cmd = Command.create(
            session=sample_session,
            command="true",
            exit_code=0,
            working_dir="/home/user",
        )

        assert cmd.is_success is True
        assert cmd.is_error is False

    def test_command_is_error(self, temp_db, sample_session):
        """Test the is_error property for failed commands."""
        cmd = Command.create(
            session=sample_session,
            command="false",
            exit_code=1,
            working_dir="/home/user",
        )

        assert cmd.is_error is True
        assert cmd.is_success is False


class TestConfig:
    """Tests for Config class."""

    def test_config_default_values(self, temp_config):
        """Test that Config loads with default values when no config exists."""
        config = Config(temp_config)

        assert config.ai_model == "zai/glm-4"
        assert config.ai_enabled is True
        assert config.get("auto_summarize") is False
        assert config.get("max_commands_per_summary") == 100
        assert config.get("export_format") == "markdown"

    def test_config_set_and_get(self, temp_config):
        """Test setting and getting configuration values."""
        config = Config(temp_config)

        config.set("custom_key", "custom_value")
        assert config.get("custom_key") == "custom_value"

    def test_config_ai_model_setter(self, temp_config):
        """Test the ai_model property setter saves to file."""
        config = Config(temp_config)
        config.ai_model = "gpt-4"

        # Reload config
        config2 = Config(temp_config)
        assert config2.ai_model == "gpt-4"

    def test_config_ai_enabled_setter(self, temp_config):
        """Test the ai_enabled property setter saves to file."""
        config = Config(temp_config)
        config.ai_enabled = False

        # Reload config
        config2 = Config(temp_config)
        assert config2.ai_enabled is False


class TestDatabaseFunctions:
    """Tests for database helper functions."""

    def test_get_active_session_returns_none_when_none(self, temp_db):
        """Test get_active_session returns None when no active session exists."""
        result = get_active_session()
        assert result is None

    def test_get_active_session_returns_session(self, temp_db):
        """Test get_active_session returns the active session."""
        session = Session.create(project="test")
        result = get_active_session()

        assert result is not None
        assert result.id == session.id

    def test_get_active_session_returns_none_after_ended(self, temp_db):
        """Test get_active_session returns None after session is ended."""
        session = Session.create(project="test")
        session.is_active = False
        session.save()

        result = get_active_session()
        assert result is None

    def test_get_or_create_session_creates_new(self, temp_db):
        """Test get_or_create_session creates a new session when none exists."""
        session = get_or_create_session(project="new-project")

        assert session is not None
        assert session.project == "new-project"
        assert session.is_active is True

    def test_get_or_create_session_returns_existing(self, temp_db):
        """Test get_or_create_session returns existing active session."""
        existing = Session.create(project="existing-project")
        session = get_or_create_session(project="different-project")

        assert session.id == existing.id
        assert session.project == "existing-project"

    def test_end_session(self, temp_db):
        """Test end_session properly ends the session."""
        session = Session.create(project="test")
        result = end_session(session)

        assert result is not None
        assert result.is_active is False
        assert result.ended_at is not None

    def test_end_session_without_param(self, temp_db):
        """Test end_session without parameters ends the active session."""
        session = Session.create(project="test")
        result = end_session()

        assert result is not None
        assert result.id == session.id
        assert result.is_active is False

    def test_end_session_returns_none_when_no_active(self, temp_db):
        """Test end_session returns None when no active session exists."""
        result = end_session()
        assert result is None


class TestLogCommand:
    """Tests for log_command function."""

    def test_log_command_with_session(self, temp_db, sample_session):
        """Test logging a command with an explicit session."""
        cmd = log_command(
            command="echo 'test'",
            exit_code=0,
            working_dir="/home/user",
            session=sample_session,
        )

        assert cmd.id is not None
        assert cmd.session.id == sample_session.id
        assert cmd.command == "echo 'test'"
        assert cmd.exit_code == 0

    def test_log_command_creates_session_if_none(self, temp_db):
        """Test log_command creates a session if none exists."""
        cmd = log_command(
            command="echo 'test'",
            exit_code=0,
            working_dir="/home/user/project",
        )

        assert cmd is not None
        assert cmd.session is not None
        assert cmd.session.is_active is True


class TestDetectProject:
    """Tests for detect_project function."""

    def test_detect_project_in_git_repo(self, mock_home):
        """Test project detection finds git repo name."""
        git_project = mock_home / "myproject"
        result = detect_project(str(git_project))

        assert result == "myproject"

    def test_detect_project_in_subdirectory(self, mock_home):
        """Test project detection works from subdirectory of git repo."""
        git_project = mock_home / "myproject"
        subdir = git_project / "src" / "components"
        subdir.mkdir(parents=True)

        result = detect_project(str(subdir))
        assert result == "myproject"

    def test_detect_project_falls_back_to_dirname(self, mock_home):
        """Test project detection falls back to directory name when no git."""
        regular_dir = mock_home / "regular_dir"
        regular_dir.mkdir(parents=True, exist_ok=True)
        # Mock Path.home() so the git walk stops at the mock home boundary
        with patch("devscribe.db.Path.home", return_value=mock_home):
            result = detect_project(str(regular_dir))

        assert result == "regular_dir"


class TestGetSessions:
    """Tests for get_sessions function."""

    def test_get_sessions_returns_all(self, temp_db):
        """Test get_sessions returns all sessions without filters."""
        Session.create(project="project1")
        Session.create(project="project2")
        Session.create(project="project3")

        sessions = get_sessions()
        assert len(sessions) == 3

    def test_get_sessions_filter_by_project(self, temp_db):
        """Test get_sessions filters by project name."""
        Session.create(project="project1")
        Session.create(project="project2")
        Session.create(project="project1")

        sessions = get_sessions(project="project1")
        assert len(sessions) == 2
        for s in sessions:
            assert s.project == "project1"

    def test_get_sessions_filter_today(self, temp_db):
        """Test get_sessions filters for today only."""
        # Create a session today
        Session.create(project="today-project")

        # Create an old session (manually set started_at)
        old_session = Session.create(project="old-project")
        old_session.started_at = datetime.now() - timedelta(days=2)
        old_session.save()

        sessions = get_sessions(today=True)
        assert len(sessions) == 1
        assert sessions[0].project == "today-project"

    def test_get_sessions_filter_last_days(self, temp_db):
        """Test get_sessions filters for last N days."""
        # Create sessions at different times
        Session.create(project="recent1")
        Session.create(project="recent2")

        old_session = Session.create(project="old")
        old_session.started_at = datetime.now() - timedelta(days=10)
        old_session.save()

        sessions = get_sessions(last_days=3)
        assert len(sessions) == 2

    def test_get_sessions_with_limit(self, temp_db):
        """Test get_sessions respects limit parameter."""
        for i in range(5):
            Session.create(project=f"project{i}")

        sessions = get_sessions(limit=3)
        assert len(sessions) == 3

    def test_get_sessions_ordered_desc(self, temp_db):
        """Test get_sessions returns sessions in descending order by date."""
        session1 = Session.create(project="first")
        session2 = Session.create(project="second")
        session3 = Session.create(project="third")

        sessions = get_sessions()
        # Most recent first
        assert sessions[0].project == "third"
        assert sessions[2].project == "first"


class TestSearchCommands:
    """Tests for search_commands function."""

    def test_search_commands_finds_matches(self, temp_db, sample_session, sample_commands):
        """Test search_commands finds commands matching the query."""
        results = search_commands("git")
        assert len(results) == 1
        assert "git" in results[0].command

    def test_search_commands_no_matches(self, temp_db, sample_session, sample_commands):
        """Test search_commands returns empty list when no matches."""
        results = search_commands("nonexistent_command_xyz")
        assert len(results) == 0

    def test_search_commands_respects_limit(self, temp_db, sample_session):
        """Test search_commands respects the limit parameter."""
        # Create multiple matching commands
        for i in range(10):
            Command.create(
                session=sample_session,
                command=f"echo 'test{i}'",
                exit_code=0,
                working_dir="/home/user",
            )

        results = search_commands("echo", limit=5)
        assert len(results) == 5

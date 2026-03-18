"""Pytest fixtures for DevScribe tests."""

import pytest
import tempfile
import os
from pathlib import Path
from peewee import SqliteDatabase
from unittest.mock import patch

from devscribe.db import Session, Command, BaseModel, db


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing.

    This fixture creates an isolated SQLite database for each test,
    ensuring tests don't interfere with the real database.
    """
    db_path = tmp_path / "test.db"
    test_db = SqliteDatabase(str(db_path))

    # Store the original database reference
    old_db = BaseModel._meta.database

    # Bind the models to the test database
    BaseModel._meta.database = test_db
    Session._meta.database = test_db
    Command._meta.database = test_db

    # Create tables
    with test_db:
        test_db.create_tables([Session, Command])

    yield test_db

    # Cleanup - clear tables and close
    with test_db:
        test_db.drop_tables([Session, Command])
    test_db.close()

    # Restore original database
    BaseModel._meta.database = old_db
    Session._meta.database = old_db
    Command._meta.database = old_db


@pytest.fixture
def temp_config(tmp_path):
    """Create a temporary config directory.

    Returns a path to a temporary config file for testing.
    """
    config_path = tmp_path / "config.json"
    return config_path


@pytest.fixture
def sample_session(temp_db):
    """Create a sample session for testing.

    Returns a Session object with test data.
    """
    session = Session.create(project="test-project")
    return session


@pytest.fixture
def sample_commands(sample_session):
    """Create sample commands for testing.

    Returns a list of Command objects associated with the sample session.
    """
    commands = [
        Command.create(
            session=sample_session,
            command="echo 'hello world'",
            exit_code=0,
            working_dir="/home/user/test-project",
        ),
        Command.create(
            session=sample_session,
            command="ls -la",
            exit_code=0,
            working_dir="/home/user/test-project",
        ),
        Command.create(
            session=sample_session,
            command="git status",
            exit_code=0,
            working_dir="/home/user/test-project",
        ),
        Command.create(
            session=sample_session,
            command="false_command",
            exit_code=1,
            working_dir="/home/user/test-project",
        ),
    ]
    return commands


@pytest.fixture
def mock_home(tmp_path):
    """Create a mock home directory structure for testing.

    Returns a path to a temporary directory simulating a home directory.
    """
    home = tmp_path / "home"
    home.mkdir()

    # Create a git project
    git_project = home / "myproject"
    git_project.mkdir()
    (git_project / ".git").mkdir()

    # Create a non-git directory
    regular_dir = home / "regular_dir"
    regular_dir.mkdir()

    return home

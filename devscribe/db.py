"""Database models and operations using Peewee ORM."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from peewee import (
    SqliteDatabase,
    Model,
    AutoField,
    DateTimeField,
    TextField,
    IntegerField,
    ForeignKeyField,
    BooleanField,
)

from devscribe import DB_PATH, CONFIG_PATH

# Initialize database
db = SqliteDatabase(str(DB_PATH))


class BaseModel(Model):
    """Base model with common functionality."""

    class Meta:
        database = db


class Session(BaseModel):
    """Represents a development session."""

    id = AutoField(primary_key=True)
    started_at = DateTimeField(default=datetime.now)
    ended_at = DateTimeField(null=True)
    project = TextField(null=True)
    summary = TextField(null=True)
    is_active = BooleanField(default=True)

    class Meta:
        table_name = "sessions"

    @property
    def duration(self) -> Optional[float]:
        """Calculate session duration in seconds."""
        if self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None

    @property
    def command_count(self) -> int:
        """Get count of commands in this session."""
        return self.commands.count()

    def get_commands(self) -> List["Command"]:
        """Get all commands for this session."""
        return list(self.commands.order_by(Command.timestamp))


class Command(BaseModel):
    """Represents a single shell command."""

    id = AutoField(primary_key=True)
    session = ForeignKeyField(Session, backref="commands", on_delete="CASCADE")
    command = TextField()
    exit_code = IntegerField()
    timestamp = DateTimeField(default=datetime.now)
    working_dir = TextField()

    class Meta:
        table_name = "commands"

    @property
    def is_success(self) -> bool:
        """Check if command executed successfully."""
        return self.exit_code == 0

    @property
    def is_error(self) -> bool:
        """Check if command failed."""
        return self.exit_code != 0


class Config:
    """Configuration management."""

    DEFAULT_CONFIG = {
        "ai_model": "zai/glm-4",
        "ai_enabled": True,
        "auto_summarize": False,
        "max_commands_per_summary": 100,
        "export_format": "markdown",
    }

    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self._config = self._load()

    def _load(self) -> dict:
        """Load configuration from file."""
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    loaded = json.load(f)
                    # Merge with defaults
                    return {**self.DEFAULT_CONFIG, **loaded}
            except (json.JSONDecodeError, IOError):
                return self.DEFAULT_CONFIG.copy()
        return self.DEFAULT_CONFIG.copy()

    def save(self) -> None:
        """Save configuration to file."""
        with open(self.path, "w") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key: str, default=None):
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value) -> None:
        """Set a configuration value."""
        self._config[key] = value
        self.save()

    @property
    def ai_model(self) -> str:
        """Get the configured AI model."""
        return self._config.get("ai_model", self.DEFAULT_CONFIG["ai_model"])

    @ai_model.setter
    def ai_model(self, value: str) -> None:
        self._config["ai_model"] = value
        self.save()

    @property
    def ai_enabled(self) -> bool:
        """Check if AI features are enabled."""
        return self._config.get("ai_enabled", True)

    @ai_enabled.setter
    def ai_enabled(self, value: bool) -> None:
        self._config["ai_enabled"] = value
        self.save()


def create_tables() -> None:
    """Create database tables if they don't exist."""
    with db:
        db.create_tables([Session, Command])


def get_active_session() -> Optional[Session]:
    """Get the currently active session, if any."""
    try:
        return Session.get(Session.is_active == True)
    except Session.DoesNotExist:
        return None


def get_or_create_session(project: Optional[str] = None) -> Session:
    """Get active session or create a new one."""
    session = get_active_session()
    if session:
        return session

    return Session.create(project=project)


def end_session(session: Optional[Session] = None) -> Optional[Session]:
    """End the specified or current active session."""
    if session is None:
        session = get_active_session()

    if session:
        session.ended_at = datetime.now()
        session.is_active = False
        session.save()
        return session
    return None


def log_command(
    command: str, exit_code: int, working_dir: str, session: Optional[Session] = None
) -> Command:
    """Log a command to the database."""
    if session is None:
        session = get_active_session()
        if session is None:
            # Auto-create session if none exists
            session = Session.create(project=detect_project(working_dir))

    return Command.create(
        session=session,
        command=command,
        exit_code=exit_code,
        working_dir=working_dir,
    )


def detect_project(working_dir: str) -> Optional[str]:
    """Detect project name from working directory (git repo name)."""
    path = Path(working_dir)
    home = Path.home()

    # Walk up the directory tree looking for .git, stop at home
    for parent in [path] + list(path.parents):
        if parent == home or parent == home.parent:
            break
        git_dir = parent / ".git"
        if git_dir.exists():
            return parent.name

    # Fall back to current directory name
    if path != home:
        return path.name
    return None


def get_sessions(
    project: Optional[str] = None,
    today: bool = False,
    last_days: Optional[int] = None,
    limit: Optional[int] = None,
) -> List[Session]:
    """Query sessions with optional filters."""
    query = Session.select()

    if project:
        query = query.where(Session.project == project)

    if today:
        today_start = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        query = query.where(Session.started_at >= today_start)

    if last_days:
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=last_days)
        query = query.where(Session.started_at >= cutoff)

    query = query.order_by(Session.started_at.desc())

    if limit:
        query = query.limit(limit)

    return list(query)


def search_commands(query: str, limit: int = 50) -> List[Command]:
    """Search for commands matching a query."""
    return list(
        Command.select()
        .where(Command.command.contains(query))
        .order_by(Command.timestamp.desc())
        .limit(limit)
    )


# Initialize database on module load
create_tables()

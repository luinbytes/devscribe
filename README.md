# ShellScribe 📝

> AI-powered terminal session logger — *git log for your whole dev life*

ShellScribe silently watches your terminal sessions and builds a searchable, AI-summarized log. Get plain-English summaries of what you built, broke, and learned.

## Features

- **🪝 Shell Hook** - Captures every command with exit codes and timestamps
- **📁 Project Detection** - Auto-tags sessions with git repo names
- **🤖 AI Summaries** - Get 5-bullet session recaps powered by LiteLLM
- **🔍 Search** - Fuzzy find through your entire command history
- **📊 Export** - Generate markdown reports of your work
- **💻 Session Tracking** - Start/stop sessions to organize your work

## Quick Start

```bash
# Clone and install
git clone https://github.com/shellscribe/shellscribe.git
cd shellscribe
./install.sh

# Start a session
shellscribe start

# Work normally... your commands are being logged

# Get an AI summary
shellscribe recap

# Search your history
shellscribe search "docker"

# Export your work
shellscribe export --last 7d -o weekly.md
```

## Installation

### Prerequisites
- Python 3.12+
- A supported shell (bash or zsh)

### Install

```bash
# Clone the repository
git clone https://github.com/shellscribe/shellscribe.git
cd shellscribe

# Run the installer
./install.sh

# Reload your shell
source ~/.bashrc  # or ~/.zshrc
```

### Manual Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .

# Install shell hook
shellscribe install
```

## Commands

### Session Management

```bash
# Start a new session (auto-detects project from git repo)
shellscribe start

# Start with explicit project name
shellscribe start my-project

# End current session
shellscribe stop

# Show session status
shellscribe status
```

### AI Features

```bash
# Get AI summary of current/last session
shellscribe recap

# Get summary of all today's sessions
shellscribe recap --today

# Explain a failed command
shellscribe recap --explain <command-id>
```

### Search & List

```bash
# List recent sessions
shellscribe list

# List today's sessions
shellscribe list --today

# List sessions from last 3 days
shellscribe list --last 3

# Filter by project
shellscribe list --project my-app

# Search commands
shellscribe search "npm install"

# Interactive search with fzf
shellscribe search "error" --interactive

# List recent commands
shellscribe list-commands

# Show only failed commands
shellscribe list-commands --failed
```

### Export

```bash
# Export last 7 days (default)
shellscribe export

# Export last 30 days
shellscribe export --last 30

# Export today only
shellscribe export --today

# Export specific project
shellscribe export --project my-app

# Export as shell script (successful commands only)
shellscribe export --script -o setup.sh
```

### Configuration

```bash
# View all config
shellscribe config --list

# Set AI model
shellscribe config ai_model zai/glm-4

# Disable AI
shellscribe config ai_enabled false
```

### Utilities

```bash
# List all projects
shellscribe projects

# Clean up old sessions
shellscribe cleanup --days 30

# Install shell hook
shellscribe install

# Uninstall shell hook
shellscribe uninstall
```

## AI Configuration

ShellScribe uses [LiteLLM](https://github.com/BerriAI/litellm) for model-agnostic AI calls.

### Supported Models

Set your preferred model with:
```bash
shellscribe config ai_model <model_name>
```

Common options:
- `zai/glm-4` - GLM-4 via ZhipuAI (default)
- `gpt-4` - OpenAI GPT-4
- `gpt-3.5-turbo` - OpenAI GPT-3.5
- `claude-3-opus-20240229` - Anthropic Claude

### API Keys

Set the appropriate environment variable:

```bash
# For ZhipuAI (default)
export ZHIPUAI_API_KEY=your_key_here

# For OpenAI
export OPENAI_API_KEY=your_key_here

# For Anthropic
export ANTHROPIC_API_KEY=your_key_here
```

Add to your `~/.bashrc` or `~/.zshrc` to persist.

## Database

ShellScribe stores data in SQLite at `~/.shellscribe/shellscribe.db`.

### Schema

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    project TEXT,
    summary TEXT,
    is_active BOOLEAN
);

CREATE TABLE commands (
    id INTEGER PRIMARY KEY,
    session_id INTEGER,
    command TEXT,
    exit_code INTEGER,
    timestamp TIMESTAMP,
    working_dir TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

## Configuration File

Location: `~/.shellscribe/config.json`

Default settings:
```json
{
    "ai_model": "zai/glm-4",
    "ai_enabled": true,
    "auto_summarize": false,
    "max_commands_per_summary": 100,
    "export_format": "markdown"
}
```

## Shell Integration

ShellScribe uses `PROMPT_COMMAND` (bash) or `precmd` hooks (zsh) to capture commands.

### How It Works

1. After each command, the hook captures:
   - The command text (from history)
   - Exit code
   - Working directory
   - Timestamp

2. This data is sent to `shellscribe log` in the background

3. Commands are associated with the active session

### Manual Hook Installation

If the automatic installation doesn't work, add this to your `~/.bashrc`:

```bash
# ShellScribe hook
export PROMPT_COMMAND='shellscribe log "$(history 1 | sed "s/^[ ]*[0-9]*[ ]*//")" "$?" "$PWD" 2>/dev/null; '"$PROMPT_COMMAND"
```

For zsh (`~/.zshrc`):

```bash
# ShellScribe hook
_shellscribe_precmd() {
    shellscribe log "$(history -1 | sed 's/^[ ]*[0-9]*[ ]*//')" "$?" "$PWD" 2>/dev/null
}
autoload -Uz add-zsh-hook
add-zsh-hook precmd _shellscribe_precmd
```

## Examples

### Daily Workflow

```bash
# Morning: start a session
shellscribe start

# Work on your project...
npm install
npm run dev
git checkout -b feature/new-ui
# ... commands are being logged ...

# End of day: get a summary
shellscribe stop
shellscribe recap

# Export your work
shellscribe export --today -o daily-standup.md
```

### Weekly Review

```bash
# Export the week's work
shellscribe export --last 7 -o weekly-report.md

# List all projects you worked on
shellscribe projects
```

### Debugging Session

```bash
# Search for error-related commands
shellscribe search "error" --interactive

# List failed commands
shellscribe list-commands --failed

# Get AI explanation of a failure
shellscribe recap --explain 123
```

## Development

### Setup

```bash
# Clone and setup dev environment
git clone https://github.com/shellscribe/shellscribe.git
cd shellscribe
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Project Structure

```
shellscribe/
├── __init__.py    # Package init, paths
├── cli.py         # Typer CLI commands
├── db.py          # Peewee models, DB ops
├── ai.py          # LiteLLM integration
├── hook.py        # Shell hook generation
└── export.py      # Markdown export
```

### Running Tests

```bash
pytest tests/
```

## Graceful Degradation

ShellScribe works without AI:
- All core logging features work without API keys
- AI commands (`recap`, `explain`) will show a helpful message
- Search, list, and export work normally

## Privacy

- All data is stored locally in `~/.shellscribe/`
- No telemetry or external calls (except AI if configured)
- You control what gets exported

## Troubleshooting

### Commands not being logged

1. Check if hook is installed:
   ```bash
   shellscribe install
   ```

2. Reload your shell:
   ```bash
   source ~/.bashrc
   ```

3. Check for active session:
   ```bash
   shellscribe status
   ```

### AI not working

1. Check API key is set:
   ```bash
   echo $ZHIPUAI_API_KEY
   ```

2. Verify AI is enabled:
   ```bash
   shellscribe config ai_enabled
   ```

### Database issues

The database is at `~/.shellscribe/shellscribe.db`. You can:
- Back it up: `cp ~/.shellscribe/shellscribe.db ~/backup/`
- Delete it to start fresh: `rm ~/.shellscribe/shellscribe.db`

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Acknowledgments

- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Rich](https://github.com/Textualize/rich) - Beautiful terminal output
- [Peewee](https://github.com/coleifer/peewee) - Simple ORM
- [LiteLLM](https://github.com/BerriAI/litellm) - Model-agnostic AI

---

**Made with ❤️ for developers who forget what they did yesterday**

"""Tests for shell hook functionality in devscribe.hook module."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from devscribe.hook import (
    HOOK_SCRIPT,
    BASH_HOOK,
    ZSH_HOOK,
    get_hook_for_shell,
    install_hook,
    uninstall_hook,
    check_hook_status,
)


class TestGetHookForShell:
    """Tests for get_hook_for_shell function."""

    def test_get_hook_for_shell_bash(self):
        """Test that get_hook_for_shell returns bash hook for 'bash'."""
        result = get_hook_for_shell("bash")

        assert result == BASH_HOOK.strip()
        assert "PROMPT_COMMAND" in result
        assert "devscribe log" in result

    def test_get_hook_for_shell_zsh(self):
        """Test that get_hook_for_shell returns zsh hook for 'zsh'."""
        result = get_hook_for_shell("zsh")

        assert result == ZSH_HOOK.strip()
        assert "add-zsh-hook" in result
        assert "precmd" in result

    def test_get_hook_for_shell_zsh_case_insensitive(self):
        """Test that get_hook_for_shell handles 'ZSH' uppercase."""
        result = get_hook_for_shell("ZSH")

        assert result == ZSH_HOOK.strip()

    def test_get_hook_for_shell_zsh_path(self):
        """Test that get_hook_for_shell detects zsh from path."""
        result = get_hook_for_shell("/bin/zsh")

        assert result == ZSH_HOOK.strip()

    def test_get_hook_for_shell_defaults_to_bash(self):
        """Test that get_hook_for_shell defaults to bash for unknown shells."""
        result = get_hook_for_shell("fish")

        assert result == BASH_HOOK.strip()

    def test_get_hook_for_shell_bash_path(self):
        """Test that get_hook_for_shell detects bash from path."""
        result = get_hook_for_shell("/usr/bin/bash")

        assert result == BASH_HOOK.strip()


class TestBashHook:
    """Tests for the bash hook script content."""

    def test_bash_hook_contains_required_elements(self):
        """Test that bash hook contains all required elements."""
        assert "# DevScribe hook" in BASH_HOOK
        assert "DEVSCRIBE_HOOK_INSTALLED" in BASH_HOOK
        assert "PROMPT_COMMAND" in BASH_HOOK
        assert "devscribe log" in BASH_HOOK

    def test_bash_hook_prevents_double_install(self):
        """Test that bash hook has guard against double installation."""
        assert 'DEVSCRIBE_HOOK_INSTALLED' in BASH_HOOK

    def test_bash_hook_captures_exit_code(self):
        """Test that bash hook captures exit code."""
        assert '"$?"' in BASH_HOOK

    def test_bash_hook_captures_working_dir(self):
        """Test that bash hook captures working directory."""
        assert '"$PWD"' in BASH_HOOK

    def test_bash_hook_suppresses_errors(self):
        """Test that bash hook suppresses errors with 2>/dev/null."""
        assert "2>/dev/null" in BASH_HOOK


class TestZshHook:
    """Tests for the zsh hook script content."""

    def test_zsh_hook_contains_required_elements(self):
        """Test that zsh hook contains all required elements."""
        assert "# DevScribe hook" in ZSH_HOOK
        assert "DEVSCRIBE_HOOK_INSTALLED" in ZSH_HOOK
        assert "_devscribe_precmd" in ZSH_HOOK
        assert "add-zsh-hook" in ZSH_HOOK

    def test_zsh_hook_uses_precmd(self):
        """Test that zsh hook uses precmd hook mechanism."""
        assert "add-zsh-hook precmd" in ZSH_HOOK

    def test_zsh_hook_uses_autoload(self):
        """Test that zsh hook uses autoload for add-zsh-hook."""
        assert "autoload -Uz add-zsh-hook" in ZSH_HOOK

    def test_zsh_hook_captures_exit_code(self):
        """Test that zsh hook captures exit code."""
        assert '"$?"' in ZSH_HOOK

    def test_zsh_hook_prevents_double_install(self):
        """Test that zsh hook has guard against double installation."""
        assert 'DEVSCRIBE_HOOK_INSTALLED' in ZSH_HOOK


class TestHookScript:
    """Tests for the combined HOOK_SCRIPT."""

    def test_hook_script_supports_bash(self):
        """Test that HOOK_SCRIPT contains bash support."""
        assert "BASH_VERSION" in HOOK_SCRIPT
        assert "PROMPT_COMMAND" in HOOK_SCRIPT

    def test_hook_script_supports_zsh(self):
        """Test that HOOK_SCRIPT contains zsh support."""
        assert "ZSH_VERSION" in HOOK_SCRIPT
        assert "add-zsh-hook" in HOOK_SCRIPT

    def test_hook_script_has_log_function(self):
        """Test that HOOK_SCRIPT defines the log function."""
        assert "_devscribe_log_command()" in HOOK_SCRIPT

    def test_hook_script_skips_devscribe_commands(self):
        """Test that HOOK_SCRIPT skips logging devscribe's own commands."""
        assert "! \"command\" =~ ^devscribe" in HOOK_SCRIPT or \
               '! "$command" =~ ^devscribe' in HOOK_SCRIPT


class TestInstallHook:
    """Tests for install_hook function."""

    def test_install_hook_dry_run(self):
        """Test install_hook with dry_run=True doesn't modify files."""
        with patch.dict('os.environ', {'SHELL': '/bin/bash'}):
            success, message = install_hook(dry_run=True)

            assert success is True
            assert "Would add hook" in message

    def test_install_hook_already_installed(self, tmp_path):
        """Test install_hook detects existing installation."""
        mock_bashrc = tmp_path / ".bashrc"
        mock_bashrc.write_text("# DevScribe - AI-powered terminal session logger\n")

        with patch.dict('os.environ', {'SHELL': '/bin/bash'}):
            with patch('pathlib.Path.home', return_value=tmp_path):
                success, message = install_hook()

                assert success is True
                assert "already installed" in message

    def test_install_hook_no_config_file(self, tmp_path):
        """Test install_hook handles missing config file."""
        with patch.dict('os.environ', {'SHELL': '/bin/bash'}):
            with patch('pathlib.Path.home', return_value=tmp_path):
                success, message = install_hook()

                # Should fail because no bashrc exists
                assert success is False
                assert "Could not find" in message

    def test_install_hook_bash(self, tmp_path):
        """Test install_hook for bash shell."""
        mock_bashrc = tmp_path / ".bashrc"
        mock_bashrc.write_text("# Existing content\n")

        with patch.dict('os.environ', {'SHELL': '/bin/bash'}):
            with patch('pathlib.Path.home', return_value=tmp_path):
                success, message = install_hook()

                assert success is True
                assert "Successfully installed" in message

                # Verify content was added
                content = mock_bashrc.read_text()
                assert "DevScribe" in content

    def test_install_hook_zsh(self, tmp_path):
        """Test install_hook for zsh shell."""
        mock_zshrc = tmp_path / ".zshrc"
        mock_zshrc.write_text("# Existing content\n")

        with patch.dict('os.environ', {'SHELL': '/bin/zsh'}):
            with patch('pathlib.Path.home', return_value=tmp_path):
                success, message = install_hook()

                assert success is True
                assert "Successfully installed" in message

                # Verify zsh hook was added
                content = mock_zshrc.read_text()
                assert "precmd" in content


class TestUninstallHook:
    """Tests for uninstall_hook function."""

    def test_uninstall_hook_not_found(self, tmp_path):
        """Test uninstall_hook when hook is not installed."""
        mock_bashrc = tmp_path / ".bashrc"
        mock_bashrc.write_text("# Regular content\n")

        with patch.dict('os.environ', {'SHELL': '/bin/bash'}):
            with patch('pathlib.Path.home', return_value=tmp_path):
                success, message = uninstall_hook()

                assert success is False
                assert "No DevScribe hook found" in message

    def test_uninstall_hook_removes_hook(self, tmp_path):
        """Test uninstall_hook removes the hook from config file."""
        mock_bashrc = tmp_path / ".bashrc"
        mock_bashrc.write_text("""
# Regular content
# DevScribe hook
if [[ -z "$DEVSCRIBE_HOOK_INSTALLED" ]]; then
    export PROMPT_COMMAND='devscribe log "$(history 1)" "$?" "$PWD"'
fi
# More content
""")

        with patch.dict('os.environ', {'SHELL': '/bin/bash'}):
            with patch('pathlib.Path.home', return_value=tmp_path):
                success, message = uninstall_hook()

                assert success is True
                assert "Removed hook" in message

                # Verify hook was removed
                content = mock_bashrc.read_text()
                assert "DevScribe hook" not in content


class TestCheckHookStatus:
    """Tests for check_hook_status function."""

    def test_check_hook_status_not_installed(self, tmp_path):
        """Test check_hook_status when hook is not installed."""
        mock_bashrc = tmp_path / ".bashrc"
        mock_bashrc.write_text("# Regular content\n")

        with patch.dict('os.environ', {'SHELL': '/bin/bash'}):
            with patch('pathlib.Path.home', return_value=tmp_path):
                installed, message = check_hook_status()

                assert installed is False
                assert "not installed" in message

    def test_check_hook_status_installed_bash(self, tmp_path):
        """Test check_hook_status detects bash hook installation."""
        mock_bashrc = tmp_path / ".bashrc"
        mock_bashrc.write_text("# DevScribe hook\ndevscribe log\n")

        with patch.dict('os.environ', {'SHELL': '/bin/bash'}):
            with patch('pathlib.Path.home', return_value=tmp_path):
                installed, message = check_hook_status()

                assert installed is True
                assert "Hook installed" in message
                assert "bash" in message

    def test_check_hook_status_installed_zsh(self, tmp_path):
        """Test check_hook_status detects zsh hook installation."""
        mock_zshrc = tmp_path / ".zshrc"
        mock_zshrc.write_text("# DevScribe hook\ndevscribe log\n")

        with patch.dict('os.environ', {'SHELL': '/bin/zsh'}):
            with patch('pathlib.Path.home', return_value=tmp_path):
                installed, message = check_hook_status()

                assert installed is True
                assert "Hook installed" in message
                assert "zsh" in message

    def test_check_hook_status_reads_existing_file(self, tmp_path):
        """Test check_hook_status properly reads config files."""
        mock_bashrc = tmp_path / ".bashrc"
        mock_bashrc.write_text("# Some config\nexport PATH=$PATH:/usr/local/bin\n")

        with patch.dict('os.environ', {'SHELL': '/bin/bash'}):
            with patch('pathlib.Path.home', return_value=tmp_path):
                installed, message = check_hook_status()

                assert installed is False

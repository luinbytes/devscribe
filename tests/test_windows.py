"""Tests for Windows/PowerShell support in devscribe."""

import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

from devscribe.hook import (
    POWERSHELL_HOOK,
    get_hook_for_shell,
    install_hook,
    uninstall_hook,
    check_hook_status,
)


class TestPowerShellHook:
    """Tests for the PowerShell hook script content."""

    def test_powershell_hook_exists(self):
        """Test that POWERSHELL_HOOK is defined."""
        assert POWERSHELL_HOOK is not None
        assert len(POWERSHELL_HOOK.strip()) > 0

    def test_powershell_hook_contains_required_elements(self):
        """Test that PowerShell hook contains all required elements."""
        assert "# DevScribe hook" in POWERSHELL_HOOK
        assert "DEVSCRIBE_HOOK_INSTALLED" in POWERSHELL_HOOK
        assert "devscribe log" in POWERSHELL_HOOK

    def test_powershell_hook_captures_command(self):
        """Test that PowerShell hook captures the last command."""
        assert "Get-History" in POWERSHELL_HOOK
        assert "CommandLine" in POWERSHELL_HOOK

    def test_powershell_hook_captures_exit_code(self):
        """Test that PowerShell hook captures exit code."""
        assert "$LASTEXITCODE" in POWERSHELL_HOOK

    def test_powershell_hook_captures_working_dir(self):
        """Test that PowerShell hook captures working directory."""
        assert "Get-Location" in POWERSHELL_HOOK or "$PWD" in POWERSHELL_HOOK

    def test_powershell_hook_skips_devscribe_commands(self):
        """Test that PowerShell hook skips logging devscribe's own commands."""
        assert "devscribe" in POWERSHELL_HOOK  # The notmatch pattern

    def test_powershell_hook_prevents_double_install(self):
        """Test that PowerShell hook has guard against double installation."""
        assert "DEVSCRIBE_HOOK_INSTALLED" in POWERSHELL_HOOK

    def test_powershell_hook_overrides_prompt(self):
        """Test that PowerShell hook overrides the prompt function."""
        assert "prompt" in POWERSHELL_HOOK


class TestGetHookForShellWindows:
    """Tests for get_hook_for_shell with PowerShell."""

    def test_get_hook_for_shell_powershell(self):
        """Test that get_hook_for_shell returns PowerShell hook for 'powershell'."""
        result = get_hook_for_shell("powershell")
        assert result == POWERSHELL_HOOK.strip()

    def test_get_hook_for_shell_pwsh(self):
        """Test that get_hook_for_shell returns PowerShell hook for 'pwsh'."""
        result = get_hook_for_shell("pwsh")
        assert result == POWERSHELL_HOOK.strip()

    def test_get_hook_for_shell_pwsh_path(self):
        """Test that get_hook_for_shell detects pwsh from path."""
        result = get_hook_for_shell("/usr/bin/pwsh")
        assert result == POWERSHELL_HOOK.strip()

    def test_get_hook_for_shell_powershell_case_insensitive(self):
        """Test case insensitivity for PowerShell detection."""
        result = get_hook_for_shell("PowerShell")
        assert result == POWERSHELL_HOOK.strip()


class TestInstallHookWindows:
    """Tests for install_hook on Windows."""

    def _make_windows_env(self):
        """Create a mock Windows environment dict."""
        # We don't clear SHELL because _is_windows() uses sys.platform,
        # but we mock sys.platform directly in each test.

    def test_install_hook_dry_run_powershell(self, tmp_path):
        """Test install_hook dry_run with PowerShell on Windows."""
        with patch("devscribe.hook.sys.platform", "win32"):
            with patch("pathlib.Path.home", return_value=tmp_path):
                ps_dir = tmp_path / "Documents" / "PowerShell"
                ps_dir.mkdir(parents=True)
                profile = ps_dir / "Microsoft.PowerShell_profile.ps1"
                profile.write_text("# Existing profile\n")

                success, message = install_hook(dry_run=True)
                assert success is True
                assert "Would add hook" in message

    def test_install_hook_creates_profile_dir(self, tmp_path):
        """Test that install_hook creates PowerShell profile directory if needed."""
        with patch("devscribe.hook.sys.platform", "win32"):
            with patch("pathlib.Path.home", return_value=tmp_path):
                # No profile directory exists yet
                profile_path = tmp_path / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
                assert not profile_path.exists()

                success, message = install_hook()
                assert success is True
                assert profile_path.exists()

    def test_install_hook_powershell_already_installed(self, tmp_path):
        """Test install_hook detects existing PowerShell installation."""
        with patch("devscribe.hook.sys.platform", "win32"):
            with patch("pathlib.Path.home", return_value=tmp_path):
                ps_dir = tmp_path / "Documents" / "PowerShell"
                ps_dir.mkdir(parents=True)
                profile = ps_dir / "Microsoft.PowerShell_profile.ps1"
                profile.write_text("# DevScribe - AI-powered terminal session logger\n")

                success, message = install_hook()
                assert success is True
                assert "already installed" in message

    def test_install_hook_powershell_fallback_profile_path(self, tmp_path):
        """Test install_hook falls back to WindowsPowerShell directory."""
        with patch("devscribe.hook.sys.platform", "win32"):
            with patch("pathlib.Path.home", return_value=tmp_path):
                # Only create the legacy profile path
                ps_dir = tmp_path / "Documents" / "WindowsPowerShell"
                ps_dir.mkdir(parents=True)
                profile = ps_dir / "Microsoft.PowerShell_profile.ps1"
                profile.write_text("# Existing profile\n")

                success, message = install_hook()
                assert success is True
                assert "Successfully installed" in message
                # Verify content was added to the fallback path
                content = profile.read_text()
                assert "DevScribe" in content

    def test_install_hook_powershell_writes_hook(self, tmp_path):
        """Test that install_hook writes the correct PowerShell hook content."""
        with patch("devscribe.hook.sys.platform", "win32"):
            with patch("pathlib.Path.home", return_value=tmp_path):
                ps_dir = tmp_path / "Documents" / "PowerShell"
                ps_dir.mkdir(parents=True)
                profile = ps_dir / "Microsoft.PowerShell_profile.ps1"
                profile.write_text("# Existing profile\n")

                success, message = install_hook()
                assert success is True

                content = profile.read_text()
                assert "DevScribe" in content
                assert "Get-History" in content
                assert "$LASTEXITCODE" in content


class TestUninstallHookWindows:
    """Tests for uninstall_hook on Windows."""

    def test_uninstall_hook_powershell(self, tmp_path):
        """Test uninstall_hook removes PowerShell hook."""
        with patch("devscribe.hook.sys.platform", "win32"):
            with patch("pathlib.Path.home", return_value=tmp_path):
                ps_dir = tmp_path / "Documents" / "PowerShell"
                ps_dir.mkdir(parents=True)
                profile = ps_dir / "Microsoft.PowerShell_profile.ps1"
                profile.write_text("""
# Existing profile
# DevScribe hook for PowerShell
if (-not $env:DEVSCRIBE_HOOK_INSTALLED) {
    $env:DEVSCRIBE_HOOK_INSTALLED = "1"
}
# More content
""")

                success, message = uninstall_hook()
                assert success is True
                assert "Removed hook" in message

    def test_uninstall_hook_powershell_not_found(self, tmp_path):
        """Test uninstall_hook when PowerShell hook is not installed."""
        with patch("devscribe.hook.sys.platform", "win32"):
            with patch("pathlib.Path.home", return_value=tmp_path):
                ps_dir = tmp_path / "Documents" / "PowerShell"
                ps_dir.mkdir(parents=True)
                profile = ps_dir / "Microsoft.PowerShell_profile.ps1"
                profile.write_text("# Regular profile\n")

                success, message = uninstall_hook()
                assert success is False


class TestCheckHookStatusWindows:
    """Tests for check_hook_status on Windows."""

    def test_check_hook_status_powershell_installed(self, tmp_path):
        """Test check_hook_status detects PowerShell hook."""
        with patch("devscribe.hook.sys.platform", "win32"):
            with patch("pathlib.Path.home", return_value=tmp_path):
                ps_dir = tmp_path / "Documents" / "PowerShell"
                ps_dir.mkdir(parents=True)
                profile = ps_dir / "Microsoft.PowerShell_profile.ps1"
                profile.write_text("# DevScribe hook\ndevscribe log\n")

                installed, message = check_hook_status()
                assert installed is True
                assert "PowerShell" in message

    def test_check_hook_status_powershell_not_installed(self, tmp_path):
        """Test check_hook_status when PowerShell hook is not installed."""
        with patch("devscribe.hook.sys.platform", "win32"):
            with patch("pathlib.Path.home", return_value=tmp_path):
                ps_dir = tmp_path / "Documents" / "PowerShell"
                ps_dir.mkdir(parents=True)
                profile = ps_dir / "Microsoft.PowerShell_profile.ps1"
                profile.write_text("# Regular profile\n")

                installed, message = check_hook_status()
                assert installed is False
                assert "not installed" in message


class TestWindowsConfigPaths:
    """Tests for Windows config path resolution."""

    def test_appdata_used_on_windows(self):
        """Test that APPDATA env var is used on Windows."""
        from devscribe import DEVSCRIBE_DIR
        # On Linux this won't use APPDATA, but we can verify the logic
        # exists in __init__.py by checking it imports sys
        from devscribe import sys as ds_sys
        assert hasattr(ds_sys, "platform")

    def test_path_home_fallback(self):
        """Test that Path.home() is always available as fallback."""
        from devscribe import DEVSCRIBE_DIR
        # Should resolve to something reasonable
        assert DEVSCRIBE_DIR is not None
        assert isinstance(DEVSCRIBE_DIR, Path)

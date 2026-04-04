"""Shell hook for capturing commands via PROMPT_COMMAND."""

import os
import sys
import subprocess
from pathlib import Path

# Shell script that gets sourced into .bashrc/.zshrc
HOOK_SCRIPT = '''
# DevScribe - AI-powered terminal session logger
_devscribe_log_command() {
    local exit_code=$?
    local command="$(history 1 | sed 's/^[ ]*[0-9]*[ ]*//')"
    
    # Skip empty commands and devscribe's own commands
    if [[ -n "$command" && ! "$command" =~ ^devscribe ]]; then
        devscribe log "$command" "$exit_code" "$PWD" 2>/dev/null &
    fi
}

# Add to PROMPT_COMMAND (bash) or precmd (zsh)
if [[ -n "$BASH_VERSION" ]]; then
    export PROMPT_COMMAND="_devscribe_log_command${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
elif [[ -n "$ZSH_VERSION" ]]; then
    autoload -Uz add-zsh-hook
    _devscribe_zsh_hook() {
        _devscribe_log_command
    }
    add-zsh-hook precmd _devscribe_zsh_hook
fi
'''

# Alternative simpler hook for bash
BASH_HOOK = '''
# DevScribe hook
if [[ -z "$DEVSCRIBE_HOOK_INSTALLED" ]]; then
    export PROMPT_COMMAND='devscribe log "$(history 1 | sed "s/^[ ]*[0-9]*[ ]*//")" "$?" "$PWD" 2>/dev/null; '"$PROMPT_COMMAND"
    export DEVSCRIBE_HOOK_INSTALLED=1
fi
'''

# ZSH hook
ZSH_HOOK = '''
# DevScribe hook
if [[ -z "$DEVSCRIBE_HOOK_INSTALLED" ]]; then
    _devscribe_precmd() {
        devscribe log "$(history -1 | sed 's/^[ ]*[0-9]*[ ]*//')" "$?" "$PWD" 2>/dev/null
    }
    autoload -Uz add-zsh-hook
    add-zsh-hook precmd _devscribe_precmd
    export DEVSCRIBE_HOOK_INSTALLED=1
fi
'''

# PowerShell hook
POWERSHELL_HOOK = '''
# DevScribe hook for PowerShell
if (-not $env:DEVSCRIBE_HOOK_INSTALLED) {
    $DevScribeOriginalPrompt = $function:prompt
    function prompt {
        $lastCommand = Get-History -Count 1 -ErrorAction SilentlyContinue
        if ($lastCommand -and $lastCommand.CommandLine -notmatch '^devscribe\\s') {
            devscribe log $lastCommand.CommandLine $LASTEXITCODE (Get-Location).Path 2>$null
        }
        if ($DevScribeOriginalPrompt) { & $DevScribeOriginalPrompt } else { "PS $($executionContext.SessionState.Path.CurrentLocation)> " }
    }
    $env:DEVSCRIBE_HOOK_INSTALLED = "1"
}
'''


def get_hook_for_shell(shell: str = "bash") -> str:
    """Get the appropriate hook script for the specified shell."""
    shell_lower = shell.lower()
    if "powershell" in shell_lower or "pwsh" in shell_lower:
        return POWERSHELL_HOOK.strip()
    if "zsh" in shell_lower:
        return ZSH_HOOK.strip()
    return BASH_HOOK.strip()


def _is_windows() -> bool:
    """Check if running on Windows."""
    return sys.platform == "win32"


def _get_powershell_profile() -> tuple:
    """Get the PowerShell profile path and shell name.

    Prefers PowerShell 7+ profile, falls back to Windows PowerShell 5.1.
    Returns (profile_path, shell_name) tuple.
    """
    home = Path.home()
    candidates = [
        (home / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1", "PowerShell"),
        (home / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1", "PowerShell"),
    ]
    for path, name in candidates:
        if path.exists():
            return path, name
    # Return preferred path even if it doesn't exist yet
    return candidates[0]


def install_hook(dry_run: bool = False) -> tuple[bool, str]:
    """
    Install the shell hook into the user's shell configuration.
    
    Returns:
        tuple: (success, message)
    """
    if _is_windows():
        config_file, shell_name = _get_powershell_profile()
        hook = POWERSHELL_HOOK.strip()
        
        # Ensure parent directory exists
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if already installed
        if config_file.exists():
            try:
                content = config_file.read_text()
                if "DevScribe" in content or "devscribe log" in content:
                    return True, f"Hook already installed in {config_file}"
            except IOError as e:
                return False, f"Could not read {config_file}: {e}"
        
        if dry_run:
            return True, f"Would add hook to {config_file}\n\nHook content:\n{hook}"
        
        # Create or append to profile
        try:
            mode = "a" if config_file.exists() else "w"
            with open(config_file, mode) as f:
                f.write("\n# DevScribe - AI-powered terminal session logger\n")
                f.write(hook)
                f.write("\n")
            
            return True, f"""Successfully installed hook to {config_file}

To activate, restart your PowerShell session.
Or run:  . {config_file}"""
        
        except IOError as e:
            return False, f"Could not write to {config_file}: {e}"
    
    # Unix (bash/zsh) path
    shell = os.environ.get("SHELL", "/bin/bash")
    home = Path.home()
    
    # Determine which config file to use
    if "zsh" in shell:
        config_file = home / ".zshrc"
        hook = ZSH_HOOK.strip()
        shell_name = "zsh"
    else:
        config_file = home / ".bashrc"
        hook = BASH_HOOK.strip()
        shell_name = "bash"
    
    if not config_file.exists():
        # Try alternative config files
        alternatives = [".bash_profile", ".profile"] if "bash" in shell else [".zprofile"]
        for alt in alternatives:
            alt_path = home / alt
            if alt_path.exists():
                config_file = alt_path
                break
        else:
            return False, f"Could not find shell config file. Tried {config_file}"
    
    # Check if already installed
    try:
        content = config_file.read_text()
        if "DevScribe" in content or "devscribe log" in content:
            return True, f"Hook already installed in {config_file}"
    except IOError as e:
        return False, f"Could not read {config_file}: {e}"
    
    if dry_run:
        return True, f"Would add hook to {config_file}\n\nHook content:\n{hook}"
    
    # Add the hook
    try:
        with open(config_file, "a") as f:
            f.write("\n# DevScribe - AI-powered terminal session logger\n")
            f.write(hook)
            f.write("\n")
        
        return True, f"""Successfully installed hook to {config_file}

To activate, run:
    source {config_file}

Or restart your terminal."""
    
    except IOError as e:
        return False, f"Could not write to {config_file}: {e}"


def uninstall_hook() -> tuple[bool, str]:
    """
    Remove the shell hook from the user's shell configuration.
    
    Returns:
        tuple: (success, message)
    """
    removed = False
    messages = []
    
    if _is_windows():
        # Check PowerShell profile paths
        config_files = [
            Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
            Path.home() / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
        ]
    else:
        shell = os.environ.get("SHELL", "/bin/bash")
        if "zsh" in shell:
            config_files = [Path.home() / ".zshrc", Path.home() / ".zprofile"]
        else:
            config_files = [Path.home() / ".bashrc", Path.home() / ".bash_profile", Path.home() / ".profile"]
    
    for config_file in config_files:
        if not config_file.exists():
            continue
        
        try:
            content = config_file.read_text()
            
            if "DevScribe" not in content and "devscribe log" not in content:
                continue
            
            # Remove the hook section
            lines = content.split("\n")
            new_lines = []
            skip_until_empty = False
            in_devscribe_block = False
            
            for line in lines:
                # Detect start of DevScribe block
                if "# DevScribe" in line or "_devscribe" in line:
                    in_devscribe_block = True
                    skip_until_empty = True
                    continue
                
                # Skip lines in the block
                if skip_until_empty:
                    # Check if this is still part of the hook
                    if ("DEVSCRIBE" in line or 
                        "_devscribe" in line or 
                        "PROMPT_COMMAND" in line and "devscribe" in line or
                        "add-zsh-hook" in line and "_devscribe" in line or
                        "precmd" in line and "_devscribe" in line):
                        continue
                    else:
                        skip_until_empty = False
                        in_devscribe_block = False
                
                if not in_devscribe_block:
                    new_lines.append(line)
            
            # Write back
            new_content = "\n".join(new_lines)
            # Clean up multiple blank lines
            while "\n\n\n" in new_content:
                new_content = new_content.replace("\n\n\n", "\n\n")
            
            config_file.write_text(new_content)
            removed = True
            messages.append(f"Removed hook from {config_file}")
            
        except IOError as e:
            messages.append(f"Could not modify {config_file}: {e}")
    
    if removed:
        return True, "\n".join(messages) + "\n\nRestart your terminal or source your config to apply changes."
    else:
        return False, "No DevScribe hook found in any config file."


def check_hook_status() -> tuple[bool, str]:
    """
    Check if the hook is installed and working.
    
    Returns:
        tuple: (installed, status_message)
    """
    if _is_windows():
        config_files = [
            (Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1", "PowerShell"),
            (Path.home() / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1", "PowerShell"),
        ]
    else:
        shell = os.environ.get("SHELL", "/bin/bash")
        if "zsh" in shell:
            config_files = [(Path.home() / ".zshrc", "zsh"), (Path.home() / ".zprofile", "zsh")]
        else:
            config_files = [(Path.home() / ".bashrc", "bash"), (Path.home() / ".bash_profile", "bash"), (Path.home() / ".profile", "bash")]
    
    for config_file, shell_name in config_files:
        if not config_file.exists():
            continue
        
        try:
            content = config_file.read_text()
            if "DevScribe" in content or "devscribe log" in content:
                return True, f"Hook installed in {config_file} for {shell_name}"
        except IOError:
            pass
    
    return False, "Hook not installed. Run 'devscribe install' to install."


if __name__ == "__main__":
    # For testing
    print(get_hook_for_shell("bash"))
    print("---")
    print(get_hook_for_shell("zsh"))
    print("---")
    print(get_hook_for_shell("powershell"))
    print("---")
    print(get_hook_for_shell("pwsh"))

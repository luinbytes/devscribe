"""Shell hook for capturing commands via PROMPT_COMMAND."""

import os
import sys
import subprocess
from pathlib import Path

# Shell script that gets sourced into .bashrc/.zshrc
HOOK_SCRIPT = '''
# ShellScribe - AI-powered terminal session logger
_shellscribe_log_command() {
    local exit_code=$?
    local command="$(history 1 | sed 's/^[ ]*[0-9]*[ ]*//')"
    
    # Skip empty commands and shellscribe's own commands
    if [[ -n "$command" && ! "$command" =~ ^shellscribe ]]; then
        shellscribe log "$command" "$exit_code" "$PWD" 2>/dev/null &
    fi
}

# Add to PROMPT_COMMAND (bash) or precmd (zsh)
if [[ -n "$BASH_VERSION" ]]; then
    export PROMPT_COMMAND="_shellscribe_log_command${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
elif [[ -n "$ZSH_VERSION" ]]; then
    autoload -Uz add-zsh-hook
    _shellscribe_zsh_hook() {
        _shellscribe_log_command
    }
    add-zsh-hook precmd _shellscribe_zsh_hook
fi
'''

# Alternative simpler hook for bash
BASH_HOOK = '''
# ShellScribe hook
if [[ -z "$SHELLSCRIBE_HOOK_INSTALLED" ]]; then
    export PROMPT_COMMAND='shellscribe log "$(history 1 | sed "s/^[ ]*[0-9]*[ ]*//")" "$?" "$PWD" 2>/dev/null; '"$PROMPT_COMMAND"
    export SHELLSCRIBE_HOOK_INSTALLED=1
fi
'''

# ZSH hook
ZSH_HOOK = '''
# ShellScribe hook
if [[ -z "$SHELLSCRIBE_HOOK_INSTALLED" ]]; then
    _shellscribe_precmd() {
        shellscribe log "$(history -1 | sed 's/^[ ]*[0-9]*[ ]*//')" "$?" "$PWD" 2>/dev/null
    }
    autoload -Uz add-zsh-hook
    add-zsh-hook precmd _shellscribe_precmd
    export SHELLSCRIBE_HOOK_INSTALLED=1
fi
'''


def get_hook_for_shell(shell: str = "bash") -> str:
    """Get the appropriate hook script for the specified shell."""
    if "zsh" in shell.lower():
        return ZSH_HOOK.strip()
    return BASH_HOOK.strip()


def install_hook(dry_run: bool = False) -> tuple[bool, str]:
    """
    Install the shell hook into the user's shell configuration.
    
    Returns:
        tuple: (success, message)
    """
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
        if "ShellScribe" in content or "shellscribe log" in content:
            return True, f"Hook already installed in {config_file}"
    except IOError as e:
        return False, f"Could not read {config_file}: {e}"
    
    if dry_run:
        return True, f"Would add hook to {config_file}\n\nHook content:\n{hook}"
    
    # Add the hook
    try:
        with open(config_file, "a") as f:
            f.write("\n# ShellScribe - AI-powered terminal session logger\n")
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
    shell = os.environ.get("SHELL", "/bin/bash")
    home = Path.home()
    
    # Check both bash and zsh configs
    config_files = []
    if "zsh" in shell:
        config_files = [home / ".zshrc", home / ".zprofile"]
    else:
        config_files = [home / ".bashrc", home / ".bash_profile", home / ".profile"]
    
    removed = False
    messages = []
    
    for config_file in config_files:
        if not config_file.exists():
            continue
        
        try:
            content = config_file.read_text()
            
            if "ShellScribe" not in content and "shellscribe log" not in content:
                continue
            
            # Remove the hook section
            lines = content.split("\n")
            new_lines = []
            skip_until_empty = False
            in_shellscribe_block = False
            
            for line in lines:
                # Detect start of ShellScribe block
                if "# ShellScribe" in line or "_shellscribe" in line:
                    in_shellscribe_block = True
                    skip_until_empty = True
                    continue
                
                # Skip lines in the block
                if skip_until_empty:
                    # Check if this is still part of the hook
                    if ("SHELLSCRIBE" in line or 
                        "_shellscribe" in line or 
                        "PROMPT_COMMAND" in line and "shellscribe" in line or
                        "add-zsh-hook" in line and "_shellscribe" in line or
                        "precmd" in line and "_shellscribe" in line):
                        continue
                    else:
                        skip_until_empty = False
                        in_shellscribe_block = False
                
                if not in_shellscribe_block:
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
        return False, "No ShellScribe hook found in any config file."


def check_hook_status() -> tuple[bool, str]:
    """
    Check if the hook is installed and working.
    
    Returns:
        tuple: (installed, status_message)
    """
    shell = os.environ.get("SHELL", "/bin/bash")
    home = Path.home()
    
    config_files = []
    if "zsh" in shell:
        config_files = [home / ".zshrc", home / ".zprofile"]
        shell_name = "zsh"
    else:
        config_files = [home / ".bashrc", home / ".bash_profile", home / ".profile"]
        shell_name = "bash"
    
    for config_file in config_files:
        if not config_file.exists():
            continue
        
        try:
            content = config_file.read_text()
            if "ShellScribe" in content or "shellscribe log" in content:
                return True, f"Hook installed in {config_file} for {shell_name}"
        except IOError:
            pass
    
    return False, "Hook not installed. Run 'shellscribe install' to install."


if __name__ == "__main__":
    # For testing
    print(get_hook_for_shell("bash"))
    print("---")
    print(get_hook_for_shell("zsh"))

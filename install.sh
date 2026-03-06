#!/bin/bash
# ShellScribe Installation Script
# Installs ShellScribe and sets up shell integration

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           ShellScribe - AI Session Logger                 ║"
echo "║                  Installation Script                      ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is required but not installed.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.12"

if [[ $(echo -e "$PYTHON_VERSION\n$REQUIRED_VERSION" | sort -V | head -n1) != "$REQUIRED_VERSION" ]]; then
    echo -e "${YELLOW}Warning: Python $REQUIRED_VERSION or higher is recommended. You have $PYTHON_VERSION.${NC}"
fi

echo -e "${GREEN}Found Python $PYTHON_VERSION${NC}"

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}Created virtual environment${NC}"
else
    echo -e "${GREEN}Virtual environment already exists${NC}"
fi

# Activate and install
echo -e "${YELLOW}Installing dependencies...${NC}"
source .venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install -e . > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Dependencies installed successfully${NC}"
else
    echo -e "${RED}Failed to install dependencies${NC}"
    exit 1
fi

# Verify installation
if ! command -v shellscribe &> /dev/null; then
    echo -e "${YELLOW}Adding shellscribe to PATH...${NC}"
    # Add to PATH for current session
    export PATH="$SCRIPT_DIR/.venv/bin:$PATH"
fi

# Install shell hook
echo -e "${YELLOW}Installing shell hook...${NC}"
shellscribe install

# Detect shell and provide instructions
SHELL_NAME=$(basename "$SHELL")
case "$SHELL_NAME" in
    bash)
        CONFIG_FILE="$HOME/.bashrc"
        ;;
    zsh)
        CONFIG_FILE="$HOME/.zshrc"
        ;;
    *)
        CONFIG_FILE="$HOME/.profile"
        ;;
esac

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Installation Complete!                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "To get started, reload your shell configuration:"
echo ""
echo -e "  ${BLUE}source $CONFIG_FILE${NC}"
echo ""
echo -e "Or restart your terminal."
echo ""
echo -e "Then start a session:"
echo ""
echo -e "  ${BLUE}shellscribe start${NC}"
echo ""
echo -e "For AI summaries, set your API key:"
echo ""
echo -e "  ${BLUE}export ZHIPUAI_API_KEY=your_key_here${NC}"
echo ""
echo -e "Available commands:"
echo -e "  ${YELLOW}shellscribe start${NC}     - Start a new session"
echo -e "  ${YELLOW}shellscribe stop${NC}      - End current session"
echo -e "  ${YELLOW}shellscribe status${NC}    - Show session status"
echo -e "  ${YELLOW}shellscribe recap${NC}     - AI summary of your work"
echo -e "  ${YELLOW}shellscribe search${NC}    - Search command history"
echo -e "  ${YELLOW}shellscribe list${NC}      - List sessions"
echo -e "  ${YELLOW}shellscribe export${NC}    - Export to markdown"
echo -e "  ${YELLOW}shellscribe --help${NC}    - Show all commands"
echo ""

# Ask about AI configuration
echo -e "${YELLOW}Would you like to configure AI features now? (y/n)${NC}"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo -e "${YELLOW}Enter your ZHIPUAI API key (or press Enter to skip):${NC}"
    read -r api_key
    if [ -n "$api_key" ]; then
        # Add to shell config
        echo "" >> "$CONFIG_FILE"
        echo "# ShellScribe AI Configuration" >> "$CONFIG_FILE"
        echo "export ZHIPUAI_API_KEY=\"$api_key\"" >> "$CONFIG_FILE"
        export ZHIPUAI_API_KEY="$api_key"
        echo -e "${GREEN}API key saved to $CONFIG_FILE${NC}"
    fi
fi

echo ""
echo -e "${GREEN}Happy logging! 📝${NC}"

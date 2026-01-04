#!/bin/bash
# Installation script for Beautiful Time Tracker

set -e

echo "Installing Beautiful Time Tracker..."

# Install system dependencies required for pycairo
echo "Checking for required system dependencies..."

# Check if pkg-config is available and cairo can be found
DEPS_NEEDED=false
if ! command -v pkg-config &> /dev/null; then
    echo "pkg-config is not installed."
    DEPS_NEEDED=true
elif ! pkg-config --exists cairo 2>/dev/null; then
    echo "Cairo development libraries are not installed."
    DEPS_NEEDED=true
else
    echo "System dependencies already installed."
fi

# Install dependencies if needed
if [ "$DEPS_NEEDED" = true ]; then
    if command -v apt-get &> /dev/null; then
        echo "Installing system dependencies with apt-get..."
        sudo apt-get update
        sudo apt-get install -y build-essential pkg-config libcairo2-dev python3-dev
    elif command -v dnf &> /dev/null; then
        echo "Installing system dependencies with dnf..."
        sudo dnf install -y gcc gcc-c++ pkg-config cairo-devel python3-devel
    elif command -v pacman &> /dev/null; then
        echo "Installing system dependencies with pacman..."
        sudo pacman -S --noconfirm base-devel pkg-config cairo python
    else
        echo "Error: Could not detect package manager."
        echo "Please install pkg-config and cairo development libraries manually:"
        echo "  For Ubuntu/Debian: sudo apt-get install build-essential pkg-config libcairo2-dev python3-dev"
        echo "  For Fedora: sudo dnf install gcc gcc-c++ pkg-config cairo-devel python3-devel"
        echo "  For Arch: sudo pacman -S base-devel pkg-config cairo python"
        exit 1
    fi
fi

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "Poetry is not installed. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -

    # Add Poetry to PATH for current session
    export PATH="$HOME/.local/bin:$PATH"

    echo ""
    echo "Poetry has been installed!"
    echo "Note: You may need to restart your terminal or run:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi

# Install Python dependencies with Poetry
echo "Installing Python dependencies with Poetry..."
poetry install --only main

# Create autostart directory if it doesn't exist
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

# Get the absolute path to this script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Update desktop file with correct path
DESKTOP_FILE="$SCRIPT_DIR/timetracker.desktop"
AUTOSTART_FILE="$AUTOSTART_DIR/timetracker.desktop"

# Create desktop file with correct paths
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=Beautiful Time Tracker
Comment=Track time spent on tasks
Exec=bash -c 'cd $SCRIPT_DIR && poetry run python timetracker.py'
Icon=org.gnome.clocks
Terminal=false
Categories=Utility;Office;
StartupNotify=true
X-GNOME-Autostart-enabled=true
EOF

# Copy to autostart
cp "$DESKTOP_FILE" "$AUTOSTART_FILE"
chmod +x "$DESKTOP_FILE"

echo "Installation complete!"
echo ""
echo "The application will now start automatically when you log in."
echo "To start it now, run:"
echo "  cd $SCRIPT_DIR && poetry run python timetracker.py"
echo ""
echo "Or simply:"
echo "  poetry run timetracker"
echo ""
echo "You can also find it in your applications menu."

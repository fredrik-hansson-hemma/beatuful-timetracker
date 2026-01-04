#!/bin/bash
# Installation script for Beautiful Time Tracker

set -e

echo "Installing Beautiful Time Tracker..."

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

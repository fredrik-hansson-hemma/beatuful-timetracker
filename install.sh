#!/bin/bash
# Installation script for Beautiful Time Tracker

set -e

echo "Installing Beautiful Time Tracker..."

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --user -r requirements.txt

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
Exec=/usr/bin/python3 $SCRIPT_DIR/timetracker.py
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
echo "To start it now, run: python3 $SCRIPT_DIR/timetracker.py"
echo ""
echo "You can also find it in your applications menu."

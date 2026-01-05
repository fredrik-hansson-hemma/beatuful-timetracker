#!/bin/bash
# Wrapper script to run timetracker with clean environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Unset snap-related GTK variables that interfere with system GTK
unset GTK_EXE_PREFIX
unset GTK_PATH
unset GDK_PIXBUF_MODULE_FILE
unset GDK_PIXBUF_MODULEDIR
unset GSETTINGS_SCHEMA_DIR

# Add Poetry to PATH
export PATH="$HOME/.local/bin:$PATH"

# Run the timetracker
cd "$SCRIPT_DIR"
poetry run python timetracker.py "$@"

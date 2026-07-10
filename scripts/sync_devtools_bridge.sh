#!/bin/sh
# Mirrors Chrome's DevToolsActivePort into the workspace so the sandboxed
# chrome-devtools-mcp server can discover the WebSocket endpoint without
# reading ~/Library. Run by launchd (com.fina-agent.chrome-devtools-bridge)
# whenever Chrome rewrites the file, i.e. on every Chrome restart.
SRC="$HOME/Library/Application Support/Google/Chrome/DevToolsActivePort"
DST_DIR="$HOME/src/fina-agent/tmp/chrome_bridge"
DST="$DST_DIR/DevToolsActivePort"

mkdir -p "$DST_DIR"
if [ -f "$SRC" ]; then
    cp "$SRC" "$DST"
else
    # Chrome deletes the file on exit; remove the copy so the MCP server
    # fails fast instead of dialing a dead endpoint.
    rm -f "$DST"
fi

#!/bin/sh
# Entry point for the chrome_devtools MCP server in Antigravity.
#
# Attaches to the user's real signed-in Chrome (Rule 1.16) via the
# chrome://inspect/#remote-debugging toggle. Chrome 144+ deliberately 404s
# the /json/* HTTP discovery endpoints in this mode; the only way in is the
# ws://127.0.0.1:<port>/devtools/browser/<uuid> endpoint recorded in the
# profile's DevToolsActivePort file. We mirror that file into the workspace
# (tmp/chrome_bridge) because Antigravity may sandbox this process away from
# ~/Library, then let the MCP server's --autoConnect re-read the mirror on
# every (re)connect.
REPO="/Users/ryan/src/fina-agent"

# Best-effort refresh; fails silently if ~/Library is unreadable here, in
# which case the launchd watcher (scripts/com.fina-agent.chrome-devtools-bridge.plist)
# or a manual `sh scripts/sync_devtools_bridge.sh` keeps the mirror fresh.
/bin/sh "$REPO/scripts/sync_devtools_bridge.sh" 2>/dev/null || true

exec /opt/homebrew/bin/node \
    "$REPO/node_modules/chrome-devtools-mcp/build/src/bin/chrome-devtools-mcp.js" \
    --autoConnect \
    --userDataDir "$REPO/tmp/chrome_bridge" \
    --logFile "$REPO/tmp/mcp_server.log"

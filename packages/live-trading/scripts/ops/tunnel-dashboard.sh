#!/bin/bash
# Tunnel sementara ke dashboard (127.0.0.1:8799). URL dicatat ke LOG supaya bisa dibaca script lain.
LOG=/tmp/cf-dash.log
: > "$LOG"
exec cloudflared tunnel --url http://127.0.0.1:8799 --no-autoupdate >> "$LOG" 2>&1

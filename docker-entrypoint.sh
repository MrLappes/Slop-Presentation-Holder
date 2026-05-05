#!/bin/bash
set -e

# Start virtual framebuffer
Xvfb :99 -screen 0 1920x1080x24 &
sleep 1

# Start lightweight window manager
openbox &

# Start VNC server (no password, listen on localhost only)
x11vnc -display :99 -forever -nopw -shared -rfbport 5900 -q &

# Start noVNC websocket proxy
websockify --web /usr/share/novnc 6080 localhost:5900 &

echo "============================================"
echo "  Slop Presentation Holder"
echo ""
echo "  Open in browser: http://localhost:6080"
echo "============================================"

# Launch the app
exec python slop.py

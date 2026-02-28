@echo off
echo Starting Lume and Lore Player...
echo server running at http://localhost:8000
python play.py
python -m http.server -d player 8000
pause
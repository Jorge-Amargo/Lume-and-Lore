import http.server
import socketserver
import os
import json

# Load config to know which folder to serve
with open("../book_config.json", "r") as f:
    config = json.load(f)

PORT = 8000
# Path to your book-specific output folder
DIRECTORY = os.path.join("..", "data", "output", str(config['book_id']))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

print(f"🌐 Game Previewer starting for Book {config['book_id']}...")
print(f"📍 Serving from: {DIRECTORY}")
print(f"🔗 Open your browser at: http://localhost:{PORT}")

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()
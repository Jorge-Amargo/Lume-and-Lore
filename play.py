import os
import sys
import webbrowser
import http.server
import socketserver
import threading
import time

# Configuration
PORT = 8001
# START OF CREATION
# Ensure we use the absolute path of the directory containing this script
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYER_URL = f"http://localhost:{PORT}/Player/index.html"

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve files relative to the ROOT_DIR defined above
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

def start_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
        print(f"🎮 Server started at http://localhost:{PORT}")
        httpd.serve_forever()
# END OF CREATION

if __name__ == "__main__":
    # Start server in background
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    time.sleep(1)
    print(f"🚀 Launching browser: {PLAYER_URL}")
    webbrowser.open(PLAYER_URL)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping server...")
        sys.exit(0)
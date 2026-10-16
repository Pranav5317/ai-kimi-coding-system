#!/usr/bin/env python3
import http.server
import socketserver
import os
import sys

# Change to the frontend directory
try:
    os.chdir('frontend')
    print("Changed to frontend directory")
    
    # Test if index.html exists
    if os.path.exists('index.html'):
        print("✓ index.html found")
    else:
        print("✗ index.html not found")
        sys.exit(1)
        
    PORT = 8000
    
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Frontend server running at http://localhost:{PORT}/")
        print("Press Ctrl+C to stop the server")
        httpd.serve_forever()
        
except Exception as e:
    print(f"Error starting frontend server: {e}")
    sys.exit(1)
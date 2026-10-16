#!/usr/bin/env python3
import http.server
import socketserver
import os

# Change to the frontend directory
os.chdir('frontend')

PORT = 8080

Handler = http.server.SimpleHTTPRequestHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Frontend server running at http://localhost:{PORT}/")
    print("Serving files from frontend directory...")
    httpd.serve_forever()
#!/usr/bin/env python3
"""
Simple HTTP server for serving the web demo
This avoids CORS issues with file:// origins
"""

import http.server
import socketserver
import webbrowser
import os
import sys

PORT = 8081

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers for local development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

def main():
    # Change to demo directory
    demo_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(demo_dir)
    
    # Start server
    with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
        print(f"🌐 Serving web demo at http://localhost:{PORT}")
        print(f"📁 Serving from: {demo_dir}")
        print(f"🚀 Opening web demo in browser...")
        print(f"   Direct link: http://localhost:{PORT}/web_demo.html")
        print("")
        print("Press Ctrl+C to stop the server")
        
        # Open browser
        try:
            webbrowser.open(f"http://localhost:{PORT}/web_demo.html")
        except:
            print("Could not open browser automatically")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped")

if __name__ == "__main__":
    main()

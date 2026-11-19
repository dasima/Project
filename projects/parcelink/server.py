"""Serve the self-contained demo locally without installing dependencies."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import argparse
import os

parser = argparse.ArgumentParser(description="集运通 Demo 本地服务器")
parser.add_argument("--port", type=int, default=8765)
args = parser.parse_args()
os.chdir(Path(__file__).resolve().parent)

class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

print(f"集运通静态 Demo: http://localhost:{args.port}/?demo=1", flush=True)
ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()

#!/usr/bin/env python3
"""
Simple HTTP server for ranch camera gallery
Serves compressed images from /home/pi/camera/gallery
"""

import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import logging

# Configuration
GALLERY_DIR = Path('/home/pi/camera/gallery')
HTML_FILE = Path('/home/pi/gallery.html')
PORT = 8080

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class GalleryHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for gallery."""

    def do_GET(self):
        """Handle GET requests."""

        # Serve main gallery page
        if self.path == '/' or self.path == '/index.html':
            self.serve_html()

        # API: Get list of images
        elif self.path == '/images':
            self.serve_image_list()

        # Serve gallery images
        elif self.path.startswith('/gallery/'):
            self.serve_gallery_image()

        else:
            self.send_error(404, "Not Found")

    def serve_html(self):
        """Serve the gallery HTML page."""
        try:
            with open(HTML_FILE, 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)

        except Exception as e:
            logger.error(f"Error serving HTML: {e}")
            self.send_error(500, str(e))

    def serve_image_list(self):
        """Serve JSON list of available images."""
        try:
            if not GALLERY_DIR.exists():
                images = []
            else:
                images = sorted([f.name for f in GALLERY_DIR.glob('*.jpg')])

            content = json.dumps(images).encode()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)

        except Exception as e:
            logger.error(f"Error listing images: {e}")
            self.send_error(500, str(e))

    def serve_gallery_image(self):
        """Serve an image from the gallery directory."""
        try:
            # Extract filename from path
            filename = self.path.split('/')[-1]
            filepath = GALLERY_DIR / filename

            if not filepath.exists() or not filepath.is_file():
                self.send_error(404, "Image not found")
                return

            # Security check: ensure file is in gallery directory
            if not filepath.resolve().is_relative_to(GALLERY_DIR.resolve()):
                self.send_error(403, "Forbidden")
                return

            with open(filepath, 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', len(content))
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            self.wfile.write(content)

        except Exception as e:
            logger.error(f"Error serving image: {e}")
            self.send_error(500, str(e))

    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info("%s - %s" % (self.client_address[0], format % args))


def main():
    """Start the HTTP server."""
    logger.info("=" * 50)
    logger.info("Ranch Camera Gallery Server")
    logger.info(f"Gallery directory: {GALLERY_DIR}")
    logger.info(f"HTML file: {HTML_FILE}")
    logger.info(f"Port: {PORT}")
    logger.info("=" * 50)

    # Ensure gallery directory exists
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)

    # Start server
    server = HTTPServer(('0.0.0.0', PORT), GalleryHandler)
    logger.info(f"Server running on http://0.0.0.0:{PORT}")
    logger.info("Access from WiFi hotspot: http://10.42.0.1:8080")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.shutdown()


if __name__ == '__main__':
    main()

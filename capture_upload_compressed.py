#!/usr/bin/env python3
"""
Trail Camera Capture & Upload Service
For Pi Zero with IMX708 Camera - Cellular Optimized with Compression
"""

import os
import sys
import time
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Optional Supabase upload
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# Configuration from environment
CAPTURE_INTERVAL = int(os.environ.get('CAPTURE_INTERVAL', 300))  # 5 minutes default
IMAGE_WIDTH = os.environ.get('IMAGE_WIDTH', '2304')
IMAGE_HEIGHT = os.environ.get('IMAGE_HEIGHT', '1296')
IMAGE_RESOLUTION = os.environ.get('IMAGE_RESOLUTION', f'{IMAGE_WIDTH}x{IMAGE_HEIGHT}')
IMAGE_QUALITY = int(os.environ.get('IMAGE_QUALITY', 10))  # JPEG quality 0-100, 10 gives ~118KB
DEVICE_NAME = os.environ.get('DEVICE_NAME', 'tophand-zero-04')

# Supabase config
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
SUPABASE_BUCKET = os.environ.get('SUPABASE_BUCKET', 'pi-zero-images')

# Paths
IMAGE_DIR = Path(os.environ.get('IMAGE_DIR', '/home/pi/camera/images'))
ARCHIVE_DIR = Path(os.environ.get('ARCHIVE_DIR', '/home/pi/camera/archive'))
GALLERY_DIR = Path(os.environ.get('GALLERY_DIR', '/home/pi/camera/gallery'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_supabase() -> Client | None:
    """Initialize Supabase client if credentials are available."""
    if not SUPABASE_AVAILABLE:
        logger.warning("Supabase library not installed, upload disabled")
        return None

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase credentials not configured, upload disabled")
        return None

    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info(f"Supabase client initialized for bucket: {SUPABASE_BUCKET}")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase: {e}")
        return None


def capture_image() -> tuple[Path | None, Path | None]:
    """Capture high-quality image and create compressed version for upload.

    Returns:
        tuple: (high_quality_filepath, compressed_filepath)
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename_hq = f"{DEVICE_NAME}_{timestamp}_HQ.jpg"
    filename_compressed = f"{DEVICE_NAME}_{timestamp}.jpg"
    filepath_hq = IMAGE_DIR / filename_hq
    filepath_compressed = IMAGE_DIR / filename_compressed

    # Parse resolution
    width, height = IMAGE_RESOLUTION.split('x')

    # Capture high-quality image first (default quality ~95)
    cmd_hq = [
        'rpicam-still',
        '-o', str(filepath_hq),
        '--width', width,
        '--height', height,
        '-t', '2000',  # 2 second warmup
        '--nopreview',
    ]

    try:
        logger.info(f"Capturing high-quality image: {filename_hq}")
        result = subprocess.run(cmd_hq, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            logger.error(f"Capture failed: {result.stderr}")
            return None, None

        if not filepath_hq.exists():
            logger.error("Capture command succeeded but file not found")
            return None, None

        size_kb_hq = filepath_hq.stat().st_size / 1024
        logger.info(f"Captured HQ: {filename_hq} ({size_kb_hq:.1f} KB)")

        # Create compressed version for cellular upload
        cmd_compressed = [
            'rpicam-still',
            '-o', str(filepath_compressed),
            '--width', width,
            '--height', height,
            '-q', str(IMAGE_QUALITY),  # Low quality for cellular
            '-t', '2000',
            '--nopreview',
        ]

        logger.info(f"Creating compressed version: {filename_compressed} (quality={IMAGE_QUALITY})")
        result = subprocess.run(cmd_compressed, capture_output=True, text=True, timeout=30)

        if result.returncode != 0 or not filepath_compressed.exists():
            logger.warning("Compressed version failed, will upload HQ instead")
            return filepath_hq, None

        size_kb_compressed = filepath_compressed.stat().st_size / 1024
        logger.info(f"Compressed: {filename_compressed} ({size_kb_compressed:.1f} KB)")

        return filepath_hq, filepath_compressed

    except subprocess.TimeoutExpired:
        logger.error("Capture timed out")
        return None, None
    except Exception as e:
        logger.error(f"Capture error: {e}")
        return None, None


def upload_to_supabase(client: Client, filepath: Path) -> bool:
    """Upload image to Supabase storage."""
    if not client:
        return False

    try:
        # Create path in bucket: device_name/YYYY/MM/DD/filename.jpg
        now = datetime.now()
        remote_path = f"{DEVICE_NAME}/{now.year}/{now.month:02d}/{now.day:02d}/{filepath.name}"

        with open(filepath, 'rb') as f:
            data = f.read()

        size_kb = len(data) / 1024
        logger.info(f"Uploading to: {remote_path} ({size_kb:.1f} KB)")

        response = client.storage.from_(SUPABASE_BUCKET).upload(
            remote_path,
            data,
            file_options={"content-type": "image/jpeg"}
        )

        logger.info(f"Upload successful: {filepath.name}")
        return True

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return False


def archive_image(filepath: Path):
    """Move image to archive after successful upload."""
    try:
        archive_path = ARCHIVE_DIR / filepath.name
        filepath.rename(archive_path)
        logger.info(f"Archived: {filepath.name}")
    except Exception as e:
        logger.error(f"Archive failed: {e}")


def cleanup_archive(max_files: int = 100):
    """Keep only the most recent N files in archive."""
    try:
        files = sorted(ARCHIVE_DIR.glob('*.jpg'), key=lambda f: f.stat().st_mtime)
        if len(files) > max_files:
            for f in files[:-max_files]:
                f.unlink()
                logger.info(f"Cleaned up old archive: {f.name}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


def cleanup_gallery(max_files: int = 50):
    """Keep only the most recent N compressed images in gallery."""
    try:
        files = sorted(GALLERY_DIR.glob('*.jpg'), key=lambda f: f.stat().st_mtime)
        if len(files) > max_files:
            for f in files[:-max_files]:
                f.unlink()
                logger.info(f"Cleaned up old gallery image: {f.name}")
    except Exception as e:
        logger.error(f"Gallery cleanup error: {e}")


def main():
    """Main capture loop."""
    logger.info("=" * 50)
    logger.info("Trail Camera Capture Service")
    logger.info(f"Device: {DEVICE_NAME}")
    logger.info(f"Resolution: {IMAGE_RESOLUTION}")
    logger.info(f"HQ: Full quality saved to SD card")
    logger.info(f"Upload: Quality {IMAGE_QUALITY} (~118KB for cellular)")
    logger.info("=" * 50)

    # Ensure directories exist
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize Supabase
    supabase = init_supabase()

    # Check camera availability
    logger.info("Checking camera...")
    result = subprocess.run(['rpicam-hello', '--list-cameras'], capture_output=True, text=True)
    if 'imx708' in result.stdout.lower():
        logger.info("IMX708 camera detected")
    else:
        logger.warning("Camera detection output:")
        logger.warning(result.stdout or result.stderr)

    # Single capture mode (for systemd timer)
    try:
        filepath_hq, filepath_compressed = capture_image()

        if filepath_hq:
            # Archive high-quality original immediately
            archive_image(filepath_hq)
            logger.info(f"HQ image archived to SD card: {filepath_hq.name}")

        if filepath_compressed:
            # Upload compressed version over cellular
            if supabase:
                upload_to_supabase(supabase, filepath_compressed)

            # Move compressed image to web gallery for viewing
            gallery_path = GALLERY_DIR / filepath_compressed.name
            filepath_compressed.rename(gallery_path)
            logger.info(f"Compressed image moved to gallery: {filepath_compressed.name}")

            # Cleanup old gallery images (keep last 50)
            cleanup_gallery()

        cleanup_archive()

    except Exception as e:
        logger.error(f"Capture/upload error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

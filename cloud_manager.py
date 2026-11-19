"""
Cantio - Cloud Manager
Supabase storage integration: upload, list, download/cache media.
Uses the requests library (no supabase-py dependency required).
"""
import os
import threading
from pathlib import Path

CACHE_DIR = os.path.join(os.path.expanduser("~"), "Cantio", "cache", "cloud")


def _ensure_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _headers(key):
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


def _guess_mime(filename):
    ext = Path(filename).suffix.lower()
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif", ".bmp": "image/bmp",
        ".mp4": "video/mp4", ".mov": "video/quicktime",
        ".avi": "video/x-msvideo", ".mkv": "video/x-matroska",
        ".webm": "video/webm",
    }.get(ext, "application/octet-stream")


def upload_file(url, key, bucket, local_path, progress_cb=None):
    """
    Upload local_path to Supabase bucket.
    progress_cb(bytes_sent: int, total: int) called during upload.
    Returns remote filename on success.
    """
    import requests
    _ensure_cache()
    filename = os.path.basename(local_path)
    file_size = os.path.getsize(local_path)
    upload_url = f"{url.rstrip('/')}/storage/v1/object/{bucket}/{filename}"

    headers = _headers(key)
    headers["Content-Type"] = _guess_mime(filename)

    if progress_cb:
        progress_cb(0, file_size)

    with open(local_path, "rb") as f:
        data = f.read()

    resp = requests.post(upload_url, headers=headers, data=data, timeout=120)
    if resp.status_code == 400 and "already exists" in resp.text.lower():
        # Try upsert
        upsert_url = f"{url.rstrip('/')}/storage/v1/object/{bucket}/{filename}"
        headers["x-upsert"] = "true"
        resp = requests.post(upsert_url, headers=headers, data=data, timeout=120)
    resp.raise_for_status()

    if progress_cb:
        progress_cb(file_size, file_size)

    return filename


def list_files(url, key, bucket):
    """
    List all files in Supabase bucket.
    Returns list of dicts with 'name', 'metadata', etc.
    """
    import requests
    list_url = f"{url.rstrip('/')}/storage/v1/object/list/{bucket}"
    headers = _headers(key)
    resp = requests.post(
        list_url, headers=headers,
        json={"prefix": "", "limit": 500, "offset": 0},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def download_file(url, key, bucket, filename, progress_cb=None):
    """
    Download file from Supabase bucket to local cache.
    Returns local file path. Skips download if already cached.
    """
    import requests
    _ensure_cache()

    local_path = os.path.join(CACHE_DIR, filename)
    if os.path.exists(local_path):
        if progress_cb:
            size = os.path.getsize(local_path)
            progress_cb(size, size)
        return local_path

    dl_url = f"{url.rstrip('/')}/storage/v1/object/{bucket}/{filename}"
    headers = _headers(key)

    resp = requests.get(dl_url, headers=headers, stream=True, timeout=60)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0

    with open(local_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total:
                    progress_cb(downloaded, total)

    return local_path


def delete_file(url, key, bucket, filename):
    """Delete a file from Supabase bucket."""
    import requests
    del_url = f"{url.rstrip('/')}/storage/v1/object/{bucket}/{filename}"
    headers = _headers(key)
    resp = requests.delete(del_url, headers=headers, timeout=30)
    resp.raise_for_status()
    return True


def get_public_url(url, bucket, filename):
    """Get the public URL for a file in a public bucket."""
    return f"{url.rstrip('/')}/storage/v1/object/public/{bucket}/{filename}"


def is_image(filename):
    return Path(filename).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def is_video(filename):
    return Path(filename).suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def test_connection(url, key, bucket):
    """Test Supabase connection. Returns (ok: bool, message: str)."""
    try:
        import requests
        files = list_files(url, key, bucket)
        return True, f"Connected — {len(files)} file(s) in bucket '{bucket}'"
    except ImportError:
        return False, "requests library not installed. Run: pip install requests"
    except Exception as e:
        return False, str(e)

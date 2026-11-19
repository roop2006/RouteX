"""Verify packaged models and fetch pinned upstream YOLO11n. No training."""
import gzip
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
YOLO_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt"


def prepare():
    manifest = json.loads((ROOT / "deploy/assets.json").read_text())
    for relative, expected in manifest.items():
        target = ROOT / relative
        if not target.exists():
            if relative == "yolo11n.pt":
                with urllib.request.urlopen(YOLO_URL, timeout=60) as response:
                    content = response.read(20 * 1024 * 1024)
            else:
                content = gzip.decompress(target.with_suffix(target.suffix + ".gz").read_bytes())
            if hashlib.sha256(content).hexdigest() != expected:
                raise RuntimeError(f"Checksum mismatch for {relative}")
            target.write_bytes(content)
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Checksum mismatch for {relative}; refusing unverified model")
        print(f"Verified {relative}")


if __name__ == "__main__":
    prepare()

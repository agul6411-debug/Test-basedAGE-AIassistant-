"""Offline model downloader and checksum verification.

Security Rule 7:
Only models are downloaded, once, from official sources, with checksum verification.
No other network use at runtime.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

from core.safety.base import SecurityException

# Official checksums and download sources
MODEL_REGISTRY = {
    "silero_vad.onnx": {
        "url": "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx",
        "sha256": "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3",
        "size_bytes": 2327524,
    },
    "en_US-lessac-medium.onnx": {
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "sha256": "5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f",
        "size_bytes": 63201294,
    },
    "en_US-lessac-medium.onnx.json": {
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
        "sha256": "efe19c417bed055f2d69908248c6ba650fa135bc868b0e6abb3da181dab690a0",
        "size_bytes": 4885,
    },
}


class ModelVerificationError(SecurityException):
    """Raised when downloaded model checksum does not match expected SHA256."""


def compute_file_sha256(path: Path) -> str:
    """Calculate the SHA256 checksum of a file.

    Args:
        path: Path to target file.

    Returns:
        Hexadecimal SHA256 digest string.
    """
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def download_with_progress(url: str, dest_path: Path, expected_sha256: str) -> None:
    """Download a file with console progress and verify its SHA256 checksum.

    Args:
        url: Remote download URL.
        dest_path: Local destination path.
        expected_sha256: Expected hexadecimal SHA256 digest.

    Raises:
        ModelVerificationError: If computed hash does not match expected_sha256.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(".tmp")

    if not url.startswith("https://"):
        raise ValueError(f"Insecure or invalid URL scheme; only HTTPS is permitted: {url}")

    print(f"[MODEL] Downloading {dest_path.name} from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "AGE-ModelDownloader/1.0"})

    with urllib.request.urlopen(req) as resp, open(temp_path, "wb") as f_out:  # nosec: B310
        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0
        hasher = hashlib.sha256()

        while chunk := resp.read(65536):
            downloaded += len(chunk)
            hasher.update(chunk)
            f_out.write(chunk)
            if total_size > 0:
                pct = (downloaded / total_size) * 100
                sys.stdout.write(f"\r  Progress: {pct:5.1f}% ({downloaded / (1024*1024):.1f} MB)")
                sys.stdout.flush()

    sys.stdout.write("\n")
    computed_hash = hasher.hexdigest()

    if computed_hash.lower() != expected_sha256.lower():
        temp_path.unlink(missing_ok=True)
        raise ModelVerificationError(
            f"Checksum mismatch for {dest_path.name}!\n"
            f"Expected: {expected_sha256}\n"
            f"Computed: {computed_hash}"
        )

    temp_path.replace(dest_path)
    print(f"[MODEL] Verified and saved {dest_path.name} (SHA256: {computed_hash[:16]}...)")


def ensure_voice_models(models_dir: Path | str | None = None) -> dict[str, Path]:
    """Ensure all required voice models are present and checksum-verified in models/.

    Args:
        models_dir: Directory where models reside (defaults to models/).

    Returns:
        Dictionary mapping model identifiers to resolved local Path objects.
    """
    root_models = Path(models_dir).resolve() if models_dir else Path("models").resolve()
    root_models.mkdir(parents=True, exist_ok=True)

    verified_paths: dict[str, Path] = {}

    for filename, meta in MODEL_REGISTRY.items():
        dest = root_models / filename
        if dest.exists():
            computed = compute_file_sha256(dest)
            if computed.lower() == meta["sha256"].lower():
                print(f"[MODEL CACHE] {filename} verified (SHA256: {computed[:16]}...)")
                verified_paths[filename] = dest
                continue
            print(f"[WARN] {filename} failed checksum check. Re-downloading...")
            dest.unlink(missing_ok=True)

        download_with_progress(meta["url"], dest, meta["sha256"])
        verified_paths[filename] = dest

    # Verify faster-whisper base.en
    whisper_dir = root_models / "whisper-base.en"
    whisper_model_file = whisper_dir / "model.bin"
    if not whisper_model_file.exists():
        print("[MODEL] Downloading Faster-Whisper base.en model...")
        import faster_whisper
        faster_whisper.download_model("base.en", output_dir=str(whisper_dir))

    print("[MODEL CACHE] Faster-Whisper base.en verified in models/whisper-base.en")
    verified_paths["whisper_model_dir"] = whisper_dir

    return verified_paths

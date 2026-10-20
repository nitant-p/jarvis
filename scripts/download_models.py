"""Download only the two selected model artifacts; record immutable revisions and SHA256."""

import hashlib
import json
import urllib.request
from pathlib import Path

MODELS = [
    ("ggerganov/whisper.cpp", "ggml-small.en.bin"),
    ("unsloth/Qwen3-4B-Instruct-2507-GGUF", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"),
]


def main():
    target = Path(__file__).resolve().parents[1] / "models"
    target.mkdir(exist_ok=True)
    manifest_path = target / "manifest.json"
    lock = target.parent / "models.lock.json"
    previous = (
        json.loads(lock.read_text())
        if lock.exists()
        else (json.loads(manifest_path.read_text()) if manifest_path.exists() else [])
    )
    manifest = []
    for repo, filename in MODELS:
        saved = next((m for m in previous if m["repo"] == repo and m["filename"] == filename), None)
        if saved:
            revision = saved["revision"]
        else:
            with urllib.request.urlopen(
                f"https://huggingface.co/api/models/{repo}", timeout=30
            ) as r:
                revision = json.load(r)["sha"]
        path = target / filename
        if not path.exists():
            print(f"Downloading {filename} at {revision}", flush=True)
            partial = path.with_suffix(path.suffix + ".partial")
            url = f"https://huggingface.co/{repo}/resolve/{revision}/{filename}"
            with urllib.request.urlopen(url, timeout=120) as source, partial.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            partial.replace(path)
        digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
        if saved and saved["sha256"] != digest:
            raise ValueError(f"Checksum mismatch for {filename}; remove corrupt artifact and retry")
        manifest.append(
            {"repo": repo, "filename": filename, "revision": revision, "sha256": digest}
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Verified {filename}", flush=True)


if __name__ == "__main__":
    main()

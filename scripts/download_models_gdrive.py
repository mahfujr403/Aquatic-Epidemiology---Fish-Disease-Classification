import os
import sys
from typing import Dict

try:
    import gdown
except Exception:
    gdown = None


def parse_map(env_val: str) -> Dict[str, str]:
    """Parse MODEL_DRIVE_MAP env var of form "filename:driveId,filename2:driveId2"."""
    out = {}
    if not env_val:
        return out
    parts = [p.strip() for p in env_val.split(",") if p.strip()]
    for part in parts:
        if ":" not in part:
            continue
        name, fid = part.split(":", 1)
        out[name.strip()] = fid.strip()
    return out


def extract_drive_id(val: str) -> str:
    """Extract drive id from either a raw id or a full Drive share URL."""
    if not val:
        return ""
    val = val.strip()
    # If it already looks like an id (no slashes, reasonable length), return
    if "/" not in val and "=" not in val:
        return val
    # Try common Drive URL patterns
    # e.g. https://drive.google.com/file/d/<id>/view?usp=sharing
    parts = val.split("/")
    if "d" in parts:
        try:
            idx = parts.index("d")
            return parts[idx + 1]
        except Exception:
            pass
    # Fallback: look for id= in query
    if "id=" in val:
        for part in val.split("&"):
            if part.startswith("id="):
                return part.split("=", 1)[1]
    return val


def download_models():
    if gdown is None:
        print("gdown not installed; skipping model download.")
        return

    mapping = parse_map(os.environ.get("MODEL_DRIVE_MAP", ""))
    # If no mapping provided via env, use a sensible default mapping.
    # Default: map the ensemble model filename to the Drive link you provided.
    if not mapping:
        default_drive_link = os.environ.get("MODEL_DRIVE_DEFAULT", "1CWWdr3l6J4rt7BJn3jtoeYbCyFtteJDV")
        mapping = {
            "ensemble-ResNet50-EfficientNetV2_model.h5": extract_drive_id(default_drive_link)
        }
        print("No MODEL_DRIVE_MAP set; using default MODEL_DRIVE_DEFAULT mapping.")

    os.makedirs("models", exist_ok=True)
    for filename, drive_id in mapping.items():
        dest = os.path.join("models", filename)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            print(f"Model already exists: {dest}, skipping download.")
            continue
        drive_id = extract_drive_id(drive_id)
        url = f"https://drive.google.com/uc?id={drive_id}"
        print(f"Downloading {filename} from Google Drive id {drive_id}...")
        try:
            gdown.download(url, dest, quiet=False)
        except Exception as e:
            print(f"Failed to download {filename}: {e}")


if __name__ == "__main__":
    download_models()

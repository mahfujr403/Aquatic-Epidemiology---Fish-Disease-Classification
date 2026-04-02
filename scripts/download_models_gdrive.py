import os
from typing import Dict

try:
    import gdown
except Exception:
    gdown = None


def get_base_dir():
    """Get project root directory (safe for Render & local)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_map(env_val: str) -> Dict[str, str]:
    """
    Parse MODEL_DRIVE_MAP env var
    Format: "filename:driveId,filename2:driveId2"
    """
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
    """Extract Google Drive file ID from URL or raw ID."""
    if not val:
        return ""

    val = val.strip()

    # Already looks like ID
    if "/" not in val and "=" not in val:
        return val

    # Pattern: /d/<id>/
    parts = val.split("/")
    if "d" in parts:
        try:
            return parts[parts.index("d") + 1]
        except Exception:
            pass

    # Pattern: ?id=<id>
    if "id=" in val:
        for part in val.split("&"):
            if part.startswith("id="):
                return part.split("=", 1)[1]

    return val


def download_models():
    """Download models from Google Drive if not already present."""
    if gdown is None:
        print("❌ gdown not installed. Run: pip install gdown")
        return

    BASE_DIR = get_base_dir()
    MODEL_DIR = os.path.join(BASE_DIR, "models")
    os.makedirs(MODEL_DIR, exist_ok=True)

    print(f"📁 Model directory: {MODEL_DIR}")

    # Read mapping from ENV
    mapping = parse_map(os.environ.get("MODEL_DRIVE_MAP", ""))

    # Default fallback
    if not mapping:
        default_drive = os.environ.get(
            "MODEL_DRIVE_DEFAULT",
            "1CWWdr3l6J4rt7BJn3jtoeYbCyFtteJDV"
        )
        mapping = {
            "ensemble-ResNet50-EfficientNetV2_model.h5": extract_drive_id(default_drive)
        }
        print("⚠️ Using default MODEL_DRIVE_DEFAULT mapping")

    # Download each model
    for filename, drive_val in mapping.items():
        drive_id = extract_drive_id(drive_val)
        dest_path = os.path.join(MODEL_DIR, filename)

        print(f"\n🔍 Checking: {filename}")

        # Skip if already exists and valid
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 10 * 1024 * 1024:
            print(f"✅ Already exists: {dest_path}")
            continue

        url = f"https://drive.google.com/uc?id={drive_id}"

        print(f"⬇️ Downloading from Drive ID: {drive_id}")
        print(f"📦 Saving to: {dest_path}")

        try:
            gdown.download(url, dest_path, quiet=False)

            # Verify download
            if not os.path.exists(dest_path):
                print(f"❌ Download failed: file not found after download")
                continue

            size_mb = os.path.getsize(dest_path) / (1024 * 1024)
            print(f"📊 Downloaded size: {size_mb:.2f} MB")

            if size_mb < 50:
                print("⚠️ WARNING: File too small → সম্ভবত HTML download হয়েছে!")
            else:
                print("✅ Download successful")

        except Exception as e:
            print(f"❌ Error downloading {filename}: {e}")


if __name__ == "__main__":
    download_models()
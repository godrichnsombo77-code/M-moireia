from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


BASE_DIR = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = BASE_DIR / "evidences"
PHOTOS_DIR = EVIDENCE_DIR / "photos"
VIDEOS_DIR = EVIDENCE_DIR / "videos"
LOGS_DIR = EVIDENCE_DIR / "logs"


def ensure_evidence_dirs() -> None:
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def make_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def image_similarity_key(frame, hash_size: int = 8) -> str:
    """Builds a small visual fingerprint to group similar evidence images."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
    average = float(np.mean(small))
    bits = (small > average).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:016x}"[:6]


def save_photo(frame, prefix: str = "alerte", niveau: str = "INFO") -> Path:
    ensure_evidence_dirs()
    cluster = image_similarity_key(frame)
    folder = PHOTOS_DIR / niveau.lower() / f"groupe_{cluster}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{prefix}_{make_timestamp()}.jpg"
    cv2.imwrite(str(path), frame)
    return path


def save_video_clip(frames: list, fps: float = 15.0, prefix: str = "sequence", niveau: str = "INFO") -> Path | None:
    if not frames:
        return None

    ensure_evidence_dirs()
    cluster = image_similarity_key(frames[0])
    folder = VIDEOS_DIR / niveau.lower() / f"groupe_{cluster}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{prefix}_{make_timestamp()}.mp4"
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    for frame in frames:
        writer.write(frame)
    writer.release()
    return path


def list_evidence_files(kind: str = "photos") -> list[Path]:
    ensure_evidence_dirs()
    directory = PHOTOS_DIR if kind == "photos" else VIDEOS_DIR
    extensions = {".jpg", ".jpeg", ".png"} if kind == "photos" else {".mp4", ".avi", ".mov", ".mkv"}
    return sorted(
        [path for path in directory.rglob("*") if path.suffix.lower() in extensions],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def evidence_groups(kind: str = "photos") -> list[dict]:
    files = list_evidence_files(kind)
    groups = {}
    for path in files:
        group = path.parent.name
        level = path.parent.parent.name if path.parent.parent != (PHOTOS_DIR if kind == "photos" else VIDEOS_DIR) else "non_classe"
        key = f"{level}/{group}"
        groups.setdefault(key, {"niveau": level, "groupe": group, "nombre": 0, "dernier_fichier": ""})
        groups[key]["nombre"] += 1
        if not groups[key]["dernier_fichier"]:
            groups[key]["dernier_fichier"] = str(path.resolve())
    return list(groups.values())

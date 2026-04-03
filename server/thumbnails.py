import os
import re
import json
import subprocess

THUMBS_DIR = "cache/thumbs"
THUMB_COUNT = 3
THUMB_POSITIONS = [0.1, 0.5, 0.8]  # 10%, 50%, 80%


def get_thumbs_dir(file_id):
    return os.path.join(THUMBS_DIR, str(file_id))


def thumbs_exist(file_id):
    d = get_thumbs_dir(file_id)
    if not os.path.isdir(d):
        return False
    files = [f for f in os.listdir(d) if f.endswith(".jpg")]
    return len(files) == THUMB_COUNT


def invalidate_thumbs(file_id):
    import shutil
    d = get_thumbs_dir(file_id)
    if os.path.isdir(d):
        shutil.rmtree(d)


def parse_duration(media_info_json):
    try:
        info = json.loads(media_info_json) if isinstance(media_info_json, str) else media_info_json
        duration_str = info.get("container", {}).get("duration", "")
        match = re.match(r"([\d.]+)", duration_str)
        return float(match.group(1)) if match else None
    except Exception:
        return None


def generate_thumbs(file_id, file_path, media_info_json):
    duration = parse_duration(media_info_json)
    if not duration:
        return []

    out_dir = get_thumbs_dir(file_id)
    os.makedirs(out_dir, exist_ok=True)

    paths = []
    for i, pos in enumerate(THUMB_POSITIONS):
        timestamp = duration * pos
        out_path = os.path.join(out_dir, f"{i}.jpg")
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(timestamp),
            "-i", file_path,
            "-vframes", "1",
            "-q:v", "2",
            "-vf", "scale='min(1280,iw)':-1",
            out_path
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            paths.append(out_path)

    return paths


def get_or_generate_thumbs(file_id, file_path, media_info_json):
    if thumbs_exist(file_id):
        d = get_thumbs_dir(file_id)
        return sorted([os.path.join(d, f) for f in os.listdir(d) if f.endswith(".jpg")])
    return generate_thumbs(file_id, file_path, media_info_json)

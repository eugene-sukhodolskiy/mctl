import os
import json
import ffmpeg
import subprocess
from .db import upsert_file, get_all_files, get_transcoded_file_ids, get_file_by_id
from .notifications import notify


def load_config(config_file):
    os.makedirs(os.path.dirname(config_file) or '.', exist_ok=True)
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    import shutil
    example = config_file.replace('.json', '.example.json')
    if os.path.exists(example):
        shutil.copy(example, config_file)
        with open(config_file, 'r') as f:
            return json.load(f)
    return {"directories": []}


def save_config(config_file, config):
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=4)



def get_media_info_with_ffprobe(file_path):
    try:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return None

        command = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=index,codec_type,codec_name,width,height,bit_rate,channels,channel_layout",
            "-show_entries", "stream_tags=language,title",
            "-show_entries", "format=duration,bit_rate,size",
            "-of", "json", file_path
        ]

        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            print(f"ffprobe error: {result.stderr}")
            return None

        data = json.loads(result.stdout)

        format_info = data.get("format", {})
        container_duration = float(format_info.get("duration", 0))
        container_bitrate = int(format_info.get("bit_rate", 0)) // 1000 if format_info.get("bit_rate") else "Unknown"
        file_size = int(format_info.get("size", 0))

        media_info = {
            "video": [],
            "audio": [],
            "container": {
                "duration": f"{container_duration:.2f} seconds" if container_duration else "Unknown",
                "bitrate": f"{container_bitrate} Kbit/s" if container_bitrate else "Unknown",
                "size": f"{file_size / (1024**2):.2f} MB" if file_size else "Unknown"
            }
        }

        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            codec_name = stream.get("codec_name")
            stream_bitrate = int(stream.get("bit_rate", 0)) // 1000 if stream.get("bit_rate") else None
            width = stream.get("width")
            height = stream.get("height")
            channels = stream.get("channels", "Unknown")
            channel_layout = stream.get("channel_layout", "Unknown")
            language = stream.get("tags", {}).get("language", "Unknown")
            title = stream.get("tags", {}).get("title", "Unknown")
            bitrate = stream_bitrate if stream_bitrate else container_bitrate

            if codec_type == "video":
                if len(media_info["video"]) == 0:
                    bitrate_str = f"{bitrate} Kbit/s" if bitrate else "Unknown"
                else:
                    bitrate_str = "Unknown"

                media_info["video"].append({
                    "resolution": f"{width}x{height}" if width and height else "Unknown",
                    "bitrate": bitrate_str,
                    "codec": codec_name
                })
            elif codec_type == "audio":
                media_info["audio"].append({
                    "bitrate": f"{stream_bitrate} Kbit/s" if stream_bitrate else "Unknown",
                    "channels": channels,
                    "layout": channel_layout,
                    "language": language,
                    "title": title,
                    "codec": codec_name
                })

        return media_info

    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return None




# Function to list media files
def list_media_files(socketio, directories):
    media_files = []
    for directory in directories:
        if os.path.exists(directory):
            for root, _, files in os.walk(directory):
                for inx, file in enumerate(files):
                    file_path = os.path.join(root, file)

                    if not inx or not inx % 50:
                        socketio.emit("medialib-scaning-process", {
                            "message": f"Scaning: { directory }"    
                        })
                    try:
                        file_info = {
                            "name": file,
                            "path": file_path,
                            "size": os.path.getsize(file_path)
                        }
                        media_files.append(file_info)
                    except OSError as e:
                        print(f"Error accessing file {file_path}: {e}")
        else:
            print(f"Directory does not exist: {directory}")
    return media_files


def filter_media_files(media_files, allowed_formats):
    """
    Фильтрует список файлов по допустимым форматам.

    :param media_files: Список файлов, полученный из list_media_files.
    :param allowed_formats: Список допустимых форматов, например [".mp3", ".jpg"].
    :return: Отфильтрованный список файлов.
    """
    filtered_files = [
        file for file in media_files
        if any(file['name'].lower().endswith(fmt.lower()) for fmt in allowed_formats)
    ]
    return filtered_files


def human_readable_size(size_bytes):
    if size_bytes < 1024:
        return [f"{size_bytes}", "B", f"{size_bytes}"]
    elif size_bytes < 1024**2:
        return [f"{size_bytes / 1024:.2f}", "KB", f"{size_bytes}"]
    elif size_bytes < 1024**3:
        return [f"{size_bytes / 1024**2:.2f}", "MB", f"{size_bytes}"]
    else:
        return [f"{size_bytes / 1024**3:.2f}", "GB", f"{size_bytes}"]


def get_single_media_by_id(file_id):
    db_file = get_file_by_id(file_id)
    if not db_file:
        return None
    path = db_file['path']
    if not os.path.exists(path):
        return None
    media_info = get_media_info_with_ffprobe(path)
    size, size_unit, size_bytes = human_readable_size(os.path.getsize(path))
    return {
        "id": db_file["id"],
        "path": path,
        "name": db_file["name"],
        "size_bytes": size_bytes,
        "size": size,
        "size_unit": size_unit,
        "info": media_info
    }


def get_single_media_by_path(path):
    from .db import get_file_by_path
    if not os.path.exists(path):
        return None
    media_info = get_media_info_with_ffprobe(path)
    size, size_unit, size_bytes = human_readable_size(os.path.getsize(path))
    db_file = get_file_by_path(path)
    media_file = {
        "id": db_file["id"] if db_file else None,
        "path": path,
        "name": os.path.basename(path),
        "size_bytes": size_bytes,
        "size": size,
        "size_unit": size_unit,
        "info": media_info
    }

    return media_file


def get_media_from_db():
    rows = get_all_files()
    if not rows:
        return None
    transcoded_ids = get_transcoded_file_ids()
    files = []
    for row in rows:
        media_info = json.loads(row["media_info"]) if row["media_info"] else {"error": "No info"}
        size_bytes = row["size_bytes"] or 0
        size, size_unit, size_bytes_str = human_readable_size(size_bytes)
        files.append({
            "id": row["id"],
            "path": row["path"],
            "name": row["name"],
            "size": size,
            "size_unit": size_unit,
            "size_bytes": size_bytes_str,
            "info": media_info,
            "transcoded": row["id"] in transcoded_ids,
        })
    return files


def bg_scan_medialib(socketio, config, GStorage):
    GStorage["scaning_state"] = "inprogress";
    media_files = list_media_files(socketio, config.get("directories", []))

    allowed_formats = config.get("allowed_formats", [])
    socketio.emit("medialib-scaning-process", {
        "message": f"Filtering by file extension..."    
    })
    filtered_files = filter_media_files(media_files, allowed_formats)
    
    socketio.emit("medialib-scaning-process", {
        "message": f"Adding media file detail..."    
    })

    # Add detailed media info
    for file in filtered_files:
        file["size"], file["size_unit"], file["size_bytes"] = human_readable_size(file["size"])
        socketio.emit("medialib-scaning-process", {
            "message": f"Adding detail: { file["path"] }"    
        })
        file_info = get_media_info_with_ffprobe(file["path"])
        if file_info:
            file["info"] = file_info
        else:
            file["info"] = {"error": "Failed to retrieve media info"}

        upsert_file(file["path"], file["name"], int(file["size_bytes"]), file_info)

    GStorage["scaning_state"] = "inaction"

    notify(socketio, None, "info", "Media library scan complete",
           f"{len(filtered_files)} file(s) indexed")
    socketio.emit("medialib-scaning-complete", {
        "data": filtered_files
    });


def scan_medialib(config, GStorage, socketio):
    if GStorage["scaning_state"] == "inprogress":
        return GStorage["outdated_cache"]

    socketio.start_background_task(
        target = bg_scan_medialib, 
        socketio=socketio,
        config = config,
        GStorage = GStorage
    )

    pass
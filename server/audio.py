import os
import re
import subprocess
from .db import AUDIO_CODEC_EXT, create_audio_track, create_operation, update_operation, get_file_by_path
from .notifications import notify


def _get_output_ext(codec):
    return AUDIO_CODEC_EXT.get(codec.lower(), ".aac") if codec else ".aac"


def _parse_ffmpeg_time(line):
    """Extract elapsed seconds from a ffmpeg progress line (time=HH:MM:SS.ss)."""
    m = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
    if m:
        h, mn, s = m.groups()
        return int(h) * 3600 + int(mn) * 60 + float(s)
    return None


def _get_file_duration(file_path):
    """Return file duration in seconds via ffprobe, or None on failure."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=15
        )
        return float(result.stdout.strip()) if result.returncode == 0 else None
    except Exception:
        return None


def _run_ffmpeg_with_progress(cmd, total_duration, socketio, emit_progress, task_key=None):
    """
    Run ffmpeg, calling emit_progress(percent) for each parsed time line.
    Returns (returncode, stderr_tail).
    emit_progress is a callable: emit_progress(percent: int)
    If task_key is given, registers the process in state.audio_tasks so it can be terminated.
    """
    from . import state
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    if task_key is not None and task_key in state.audio_tasks:
        state.audio_tasks[task_key]["process"] = process

    output_tail = []

    for line in (process.stdout or []):
        output_tail.append(line.rstrip())
        if len(output_tail) > 40:
            output_tail.pop(0)

        if total_duration:
            t = _parse_ffmpeg_time(line)
            if t is not None:
                percent = min(int(t / total_duration * 100), 99)
                emit_progress(percent)
                socketio.sleep(0)

    process.wait()
    return process.returncode, output_tail


def extract_audio_track(socketio, file_path, track_index, track_meta, output_dir, user_id=None):
    """
    Extract a single audio track from video file.
    track_meta: dict with title, language, codec, bitrate, channels
    """
    from . import state
    task_key = f"audio-extract:{file_path}:{track_index}"
    state.audio_tasks[task_key] = {"process": None}

    db_file = get_file_by_path(file_path)
    file_id = db_file["id"] if db_file else None

    ext = _get_output_ext(track_meta.get("codec"))
    lang = track_meta.get("language", "und")
    title = track_meta.get("title") or f"track_{track_index}"
    base = os.path.splitext(os.path.basename(file_path))[0]
    out_filename = f"{base}.{lang}.{track_index}{ext}"
    out_path = os.path.join(output_dir, out_filename)

    os.makedirs(output_dir, exist_ok=True)

    operation_id = None
    if db_file:
        operation_id = create_operation(
            file_id=db_file["id"],
            op_type="extract_audio",
            params={"track_index": track_index, **track_meta},
            snapshot_before=None,
            backup_path=None
        )

    total_duration = _get_file_duration(file_path)

    socketio.emit("audio-extract-progress", {
        "file": file_path,
        "file_id": file_id,
        "track_index": track_index,
        "percent": 0,
        "message": "Extracting..."
    })

    cmd = [
        "ffmpeg", "-y",
        "-i", file_path,
        "-map", f"0:a:{track_index}",
        "-c:a", "copy",
        out_path
    ]

    def emit_progress(percent):
        socketio.emit("audio-extract-progress", {
            "file": file_path,
            "file_id": file_id,
            "track_index": track_index,
            "percent": percent,
            "message": "Extracting..."
        })

    returncode, output_tail = _run_ffmpeg_with_progress(cmd, total_duration, socketio, emit_progress, task_key)

    if returncode == 0:
        state.audio_tasks.pop(task_key, None)
        track_id = None
        if db_file:
            update_operation(operation_id, "completed")
            track_id = create_audio_track(
                source_file_id=db_file["id"],
                track_index=track_index,
                title=title,
                language=lang,
                codec=track_meta.get("codec"),
                bitrate=track_meta.get("bitrate"),
                channels=track_meta.get("channels"),
                path=out_path
            )
        file_name = os.path.basename(file_path)
        notify(socketio, user_id, "success", f"Audio track extracted: {file_name}",
               f"Track {track_index} → {out_filename}")
        socketio.emit("audio-extract-completed", {
            "file": file_path,
            "file_id": file_id,
            "track_index": track_index,
            "track_id": track_id
        })
    else:
        was_canceled = task_key not in state.audio_tasks
        state.audio_tasks.pop(task_key, None)
        if was_canceled:
            if operation_id:
                update_operation(operation_id, "canceled")
            if os.path.exists(out_path):
                os.remove(out_path)
            socketio.emit("audio-extract-canceled", {
                "file": file_path,
                "file_id": file_id,
                "track_index": track_index
            })
        else:
            if operation_id:
                update_operation(operation_id, "failed")
            err_msg = "\n".join(output_tail[-10:]) if output_tail else "Unknown error"
            notify(socketio, user_id, "error", f"Audio extract failed: {os.path.basename(file_path)}", err_msg)
            socketio.emit("audio-extract-error", {
                "file": file_path,
                "file_id": file_id,
                "track_index": track_index,
                "message": err_msg
            })


def remove_audio_track(socketio, file_path, track_index, user_id=None):
    """Remove one audio track from video, remux in place."""
    from . import state
    task_key = f"audio-remove:{file_path}:{track_index}"
    state.audio_tasks[task_key] = {"process": None}

    db_file = get_file_by_path(file_path)
    file_id = db_file["id"] if db_file else None
    base, ext = os.path.splitext(file_path)
    tmp_path = base + ".removing" + ext

    operation_id = None
    if db_file:
        operation_id = create_operation(
            file_id=db_file["id"],
            op_type="remove_audio",
            params={"track_index": track_index},
            snapshot_before=None,
            backup_path=None
        )

    total_duration = _get_file_duration(file_path)

    socketio.emit("audio-remove-progress", {
        "file": file_path,
        "file_id": file_id,
        "track_index": track_index,
        "percent": 0,
        "message": "Removing audio track..."
    })

    cmd = [
        "ffmpeg", "-y",
        "-i", file_path,
        "-map", "0",
        "-map", f"-0:a:{track_index}",
        "-c", "copy",
        tmp_path
    ]

    def emit_progress(percent):
        socketio.emit("audio-remove-progress", {
            "file": file_path,
            "file_id": file_id,
            "track_index": track_index,
            "percent": percent,
            "message": "Removing audio track..."
        })

    returncode, output_tail = _run_ffmpeg_with_progress(cmd, total_duration, socketio, emit_progress, task_key)

    if returncode == 0:
        state.audio_tasks.pop(task_key, None)
        os.replace(tmp_path, file_path)
        if operation_id:
            update_operation(operation_id, "completed")
        notify(socketio, user_id, "success", f"Audio track removed: {os.path.basename(file_path)}",
               f"Track index {track_index} removed")
        socketio.emit("audio-remove-completed", {
            "file": file_path,
            "file_id": file_id,
            "track_index": track_index
        })
    else:
        was_canceled = task_key not in state.audio_tasks
        state.audio_tasks.pop(task_key, None)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if was_canceled:
            if operation_id:
                update_operation(operation_id, "canceled")
            socketio.emit("audio-remove-canceled", {
                "file": file_path,
                "file_id": file_id,
                "track_index": track_index
            })
        else:
            if operation_id:
                update_operation(operation_id, "failed")
            err_msg = "\n".join(output_tail[-10:]) if output_tail else "Unknown error"
            notify(socketio, user_id, "error", f"Audio remove failed: {os.path.basename(file_path)}", err_msg)
            socketio.emit("audio-remove-error", {
                "file": file_path,
                "file_id": file_id,
                "track_index": track_index,
                "message": err_msg
            })


def add_audio_track(socketio, file_path, audio_track_path, video_duration, track_title='', user_id=None):
    """
    Add an external audio track to a video file.
    Syncs audio to video duration: trims if longer, pads with silence if shorter.
    """
    from . import state
    task_key = f"audio-add:{file_path}"
    state.audio_tasks[task_key] = {"process": None}

    db_file = get_file_by_path(file_path)
    file_id = db_file["id"] if db_file else None
    base, ext = os.path.splitext(file_path)
    tmp_path = base + ".adding_audio" + ext

    operation_id = None
    if db_file:
        operation_id = create_operation(
            file_id=db_file["id"],
            op_type="add_audio",
            params={"audio_source": audio_track_path},
            snapshot_before=None,
            backup_path=None
        )

    socketio.emit("audio-add-progress", {
        "file": file_path,
        "file_id": file_id,
        "percent": 0,
        "message": "Adding audio track..."
    })

    # Build audio filter for sync: trim to video duration + pad if shorter
    audio_filter = f"atrim=0:{video_duration},apad=whole_dur={video_duration}"

    cmd = [
        "ffmpeg", "-y",
        "-i", file_path,
        "-i", audio_track_path,
        "-map", "0:v",
        "-map", "0:a",
        "-map", "1:a",
        "-filter:a:1", audio_filter,
        "-c:v", "copy",
        "-c:a", "copy",
        "-c:a:1", "aac",
    ]
    if track_title:
        cmd += ["-metadata:s:a:1", f"title={track_title}"]
    cmd.append(tmp_path)

    def emit_progress(percent):
        socketio.emit("audio-add-progress", {
            "file": file_path,
            "file_id": file_id,
            "percent": percent,
            "message": "Adding audio track..."
        })

    returncode, output_tail = _run_ffmpeg_with_progress(cmd, video_duration, socketio, emit_progress, task_key)

    if returncode == 0:
        state.audio_tasks.pop(task_key, None)
        os.replace(tmp_path, file_path)
        if operation_id:
            update_operation(operation_id, "completed")
        from .thumbnails import invalidate_thumbs
        if db_file:
            invalidate_thumbs(db_file["id"])
        notify(socketio, user_id, "success", f"Audio track added: {os.path.basename(file_path)}",
               track_title or os.path.basename(audio_track_path))
        socketio.emit("audio-add-completed", {
            "file": file_path,
            "file_id": file_id
        })
    else:
        was_canceled = task_key not in state.audio_tasks
        state.audio_tasks.pop(task_key, None)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if was_canceled:
            if operation_id:
                update_operation(operation_id, "canceled")
            socketio.emit("audio-add-canceled", {
                "file": file_path,
                "file_id": file_id
            })
        else:
            if operation_id:
                update_operation(operation_id, "failed")
            err_msg = "\n".join(output_tail[-10:]) if output_tail else "Unknown error"
            notify(socketio, user_id, "error", f"Audio add failed: {os.path.basename(file_path)}", err_msg)
            socketio.emit("audio-add-error", {
                "file": file_path,
                "file_id": file_id,
                "message": err_msg
            })

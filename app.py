from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from functools import wraps
import os
import json
from mediascan import scan_medialib, load_config, save_config, get_single_media_by_path, get_media_from_db, get_media_info_with_ffprobe
from thumbnails import get_or_generate_thumbs, invalidate_thumbs, get_thumbs_dir
from audio import extract_audio_track, remove_audio_track, add_audio_track
from db import init_db, get_file_by_path, create_operation, get_file_operations, get_operation_by_id, get_file_path_by_id, update_file_media_info, mark_backup_deleted, get_all_audio_tracks, get_audio_track_by_id, delete_audio_track, get_file_backup_paths, delete_file_record, get_latest_operation_by_backup_path, get_app_stats, get_users_count, create_user, get_user_by_username, get_user_by_id, update_user_password, get_notifications, get_unread_count, mark_notification_read, mark_all_notifications_read, delete_notification, delete_all_notifications
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import unquote
from flask_socketio import SocketIO
from transcodate import transcode_file, detect_available_accelerators


app = Flask(__name__)

# Load configuration
CONFIG_FILE = os.environ.get('MCTL_CONFIG', 'data/config.json')
config = load_config(CONFIG_FILE)

# Secret key: generate once and persist in config
if not config.get('secret_key'):
    config['secret_key'] = os.urandom(32).hex()
    save_config(CONFIG_FILE, config)
app.secret_key = config['secret_key']

socketio = SocketIO(app)

GStorage = {
    "scaning_state": "inaction"  # values: inaction, inprogress
}

transcoding_tasks = {}
available_accelerators = detect_available_accelerators()
init_db()


# AUTH

def is_file_transcoding(file_path):
    return any(t.get("file") == file_path for t in transcoding_tasks.values())


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/login', methods=['GET', 'POST'])
def login():
    if get_users_count() == 0:
        return redirect(url_for('register'))
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        data = request.json
        user = get_user_by_username(data.get('username', ''))
        if user and check_password_hash(user['password_hash'], data.get('password', '')):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return jsonify({'status': 'ok'})
        return jsonify({'error': 'Invalid username or password'}), 401
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if get_users_count() > 0:
        return redirect(url_for('login'))
    if request.method == 'POST':
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        if not username or len(password) < 6:
            return jsonify({'error': 'Username required and password must be at least 6 characters'}), 400
        if get_user_by_username(username):
            return jsonify({'error': 'Username already taken'}), 400
        create_user(username, generate_password_hash(password), is_superadmin=True)
        user = get_user_by_username(username)
        session['user_id'] = user['id']
        session['username'] = user['username']
        return jsonify({'status': 'ok'})
    return render_template('register.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if not config.get('reset_admin_password'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        data = request.json
        password = data.get('password', '')
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        # Reset password for the superadmin (first user)
        from db import get_connection
        with get_connection() as conn:
            row = conn.execute("SELECT id FROM users WHERE is_superadmin = 1 ORDER BY id LIMIT 1").fetchone()
        if not row:
            return jsonify({'error': 'No superadmin found'}), 404
        update_user_password(row['id'], generate_password_hash(password))
        config.pop('reset_admin_password', None)
        save_config(CONFIG_FILE, config)
        return jsonify({'status': 'ok'})
    return render_template('reset-password.html')


# ROUTING

@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route("/audio-tracks")
@login_required
def audio_tracks_page():
    return render_template('audio-tracks.html')


@app.route("/originals")
@login_required
def originals_page():
    return render_template('originals.html')


@app.route('/originals/list', methods=['GET'])
@login_required
def originals_list():
    backup_dir = config.get('transcoded_directory', 'transcoded_files')
    if not os.path.isdir(backup_dir):
        return jsonify([])

    result = []
    for fname in sorted(os.listdir(backup_dir)):
        fpath = os.path.join(backup_dir, fname)
        if not os.path.isfile(fpath):
            continue
        rec = get_latest_operation_by_backup_path(fpath) or {}
        result.append({
            'operation_id':  rec.get('operation_id'),
            'backup_path':   fpath,
            'backup_name':   fname,
            'size_bytes':    os.path.getsize(fpath),
            'started_at':    rec.get('started_at'),
            'source_name':   rec.get('source_name'),
            'source_path':   rec.get('source_path'),
        })

    result.sort(key=lambda x: x.get('started_at') or '', reverse=True)
    return jsonify(result)


@app.route("/single")
@login_required
def single_media():
    path = request.args.get("path", "")
    if not path:
        return "Path not provided", 400

    path_to_mediafile = unquote(path)
    media_file = get_single_media_by_path(path_to_mediafile)
    
    return render_template('single.html', file=media_file, accelerators=available_accelerators)


@app.route("/single-json")
@login_required
def single_media_json():
    path = request.args.get("path", "")
    if not path:
        return "Path not provided", 400

    path_to_mediafile = unquote(path)

    return jsonify(get_single_media_by_path(path_to_mediafile))


@app.route('/scan-status')
@login_required
def scan_status():
    return jsonify({'scanning': GStorage.get('scaning_state') == 'inprogress'})


@app.route('/file-status')
@login_required
def file_status():
    path = request.args.get('path', '')
    return jsonify({'transcoding': is_file_transcoding(path)})


@app.route('/media-list/clear-cache')
@login_required
def media_list_clear_cache():
    if GStorage["scaning_state"] == "inprogress":
        return jsonify({"status": True})

    scan_medialib(config, GStorage, socketio)
    return jsonify({"status": True})


@app.route('/media-list', methods=['GET'])
@login_required
def media_list():
    files = get_media_from_db() or []

    if GStorage["scaning_state"] == "inprogress":
        response = {"status": "scaning", "data": files}
    else:
        response = {"status": True, "data": files}
    return jsonify(response)


@app.route('/process-media', methods=['POST'])
@login_required
def process_media():
    data = request.json
    file_path = data.get('path')
    codec = data.get('codec')
    resolution = data.get('resolution')
    crf = data.get('crf')
    preset = data.get('preset-libx')
    cpu_used = data.get('preset-vp9')
    acceleration = data.get('acceleration', 'CPU')
    delete_original = data.get('delete_original', False)
    if codec == "libaom-av1":
        cpu_used = data.get('preset-av1')

    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "File path is invalid or file does not exist"}), 400

    if is_file_transcoding(file_path):
        return jsonify({"error": "File is already being transcoded"}), 409

    # Step 1: Prepare backup destination (skipped when delete_original=True — no point copying)
    if delete_original:
        dest_path = None
    else:
        dest_dir = config.get('transcoded_directory', 'transcoded_files')
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, os.path.basename(file_path))

    # Step 2: Log operation to DB
    operation_id = None
    db_file = get_file_by_path(file_path)
    if db_file:
        snapshot = json.loads(db_file["media_info"]) if db_file["media_info"] else None
        operation_id = create_operation(
            file_id=db_file["id"],
            op_type="transcoding",
            params={"codec": codec, "resolution": resolution, "crf": crf,
                    "preset": preset, "acceleration": acceleration,
                    "original_size_bytes": db_file["size_bytes"]},
            snapshot_before=snapshot,
            backup_path=dest_path
        )

    # Step 3: Start transcoding (copy happens at the beginning of the task)
    user_id = session.get('user_id')
    socketio.start_background_task(
        target=transcode_file,
        transcoding_tasks=transcoding_tasks,
        socketio=socketio,
        file_path=file_path,
        dest_path=dest_path,
        acceleration=acceleration,
        codec=codec,
        resolution=resolution,
        crf=crf,
        preset=preset,
        cpu_used=cpu_used,
        operation_id=operation_id,
        delete_original=delete_original,
        user_id=user_id
    )

    return jsonify({"status": "processing started", "file": file_path}), 202


@app.route('/stop-transcoding', methods=['GET'])
@login_required
def stop_transcoding():
    task_id = request.args.get("task_id")

    if task_id in transcoding_tasks:
        task = transcoding_tasks.pop(task_id, None)
        if task:
            task["process"].terminate()
        return jsonify({"status": "stopped", "task_id": task_id})
    
    return jsonify({"status": "error", "message": "Task not found"}), 404


@app.route('/thumbnails/<int:file_id>', methods=['GET'])
@login_required
def thumbnails(file_id):
    from db import get_connection
    with get_connection() as conn:
        row = conn.execute("SELECT path, media_info FROM files WHERE id = ?", (file_id,)).fetchone()
    if not row:
        return jsonify({"error": "File not found"}), 404

    paths = get_or_generate_thumbs(file_id, row["path"], row["media_info"])
    urls = [f"/thumbs/{file_id}/{os.path.basename(p)}" for p in paths]
    return jsonify(urls)


@app.route('/thumbs/<int:file_id>/<filename>')
@login_required
def serve_thumb(file_id, filename):
    return send_from_directory(os.path.abspath(get_thumbs_dir(file_id)), filename)


@app.route('/file-history', methods=['GET'])
@login_required
def file_history():
    path = unquote(request.args.get("path", ""))
    if not path:
        return jsonify({"error": "Path not provided"}), 400

    operations = get_file_operations(path)
    for op in operations:
        if op.get("params"):
            op["params"] = json.loads(op["params"])
        if op.get("snapshot_before"):
            op["snapshot_before"] = json.loads(op["snapshot_before"])

    return jsonify(operations)


def restore_file_task(socketio, operation_id, backup_path, file_path, user_id=None):
    CHUNK_SIZE = 1024 * 1024  # 1 MB
    tmp_path = file_path + ".restoring"
    try:
        total = os.path.getsize(backup_path)
        copied = 0

        with open(backup_path, 'rb') as src, open(tmp_path, 'wb') as dst:
            while True:
                buf = src.read(CHUNK_SIZE)
                if not buf:
                    break
                dst.write(buf)
                copied += len(buf)
                percent = int(copied / total * 100)
                socketio.emit('restore-progress', {
                    'operation_id': operation_id,
                    'percent': percent
                })

        os.replace(tmp_path, file_path)

        if os.path.exists(backup_path):
            os.remove(backup_path)
        mark_backup_deleted(operation_id)

        fresh_info = get_media_info_with_ffprobe(file_path)
        if fresh_info:
            update_file_media_info(file_path, os.path.getsize(file_path), fresh_info)

        from notifications import notify
        notify(socketio, user_id, "success", f"Original restored: {os.path.basename(file_path)}")
        socketio.emit('restore-completed', {
            'operation_id': operation_id,
            'file': file_path
        })

    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        from notifications import notify
        notify(socketio, user_id, "error", f"Restore failed: {os.path.basename(file_path)}", str(e))
        socketio.emit('restore-error', {
            'operation_id': operation_id,
            'message': str(e)
        })


@app.route('/restore-original', methods=['POST'])
@login_required
def restore_original():
    operation_id = request.json.get('operation_id')
    if not operation_id:
        return jsonify({"error": "operation_id is required"}), 400

    op = get_operation_by_id(operation_id)
    if not op:
        return jsonify({"error": "Operation not found"}), 404

    backup_path = op.get('backup_path')
    if not backup_path or not os.path.exists(backup_path):
        return jsonify({"error": "Backup file not found"}), 404

    file_path = get_file_path_by_id(op['file_id'])
    if not file_path:
        return jsonify({"error": "Original file record not found"}), 404

    socketio.start_background_task(
        target=restore_file_task,
        socketio=socketio,
        operation_id=operation_id,
        backup_path=backup_path,
        file_path=file_path,
        user_id=session.get('user_id')
    )

    return jsonify({"status": "restore started"}), 202


@app.route('/delete-file', methods=['POST'])
@login_required
def delete_file():
    file_path = request.json.get('path')
    if not file_path:
        return jsonify({"error": "path is required"}), 400

    if is_file_transcoding(file_path):
        return jsonify({"error": "Cannot delete file while transcoding is in progress"}), 409

    db_file = get_file_by_path(file_path)
    if not db_file:
        return jsonify({"error": "File not found in database"}), 404

    file_id = db_file["id"]

    # Delete all backup copies
    for backup_path in get_file_backup_paths(file_id):
        if os.path.exists(backup_path):
            os.remove(backup_path)

    # Delete thumbnail cache
    from thumbnails import invalidate_thumbs
    invalidate_thumbs(file_id)

    # Delete the video file itself
    if os.path.exists(file_path):
        os.remove(file_path)

    # Remove DB records (operations + file row), audio_tracks are kept
    delete_file_record(file_id)

    return jsonify({"status": "deleted"})


@app.route('/delete-backup', methods=['POST'])
@login_required
def delete_backup():
    data = request.json
    operation_id = data.get('operation_id')
    direct_path = data.get('backup_path')

    if operation_id:
        op = get_operation_by_id(operation_id)
        if not op:
            return jsonify({"error": "Operation not found"}), 404
        backup_path = op.get('backup_path')
        if not backup_path or not os.path.exists(backup_path):
            return jsonify({"error": "Backup file not found"}), 404
        os.remove(backup_path)
        mark_backup_deleted(operation_id)
    elif direct_path:
        if not os.path.exists(direct_path):
            return jsonify({"error": "Backup file not found"}), 404
        os.remove(direct_path)
    else:
        return jsonify({"error": "operation_id or backup_path is required"}), 400

    return jsonify({"status": "deleted"})


@app.route('/audio/extract', methods=['POST'])
@login_required
def audio_extract():
    data = request.json
    file_path = data.get('path')
    track_index = data.get('track_index')
    track_meta = data.get('track_meta', {})

    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 400
    if track_index is None:
        return jsonify({"error": "track_index is required"}), 400
    if is_file_transcoding(file_path):
        return jsonify({"error": "Audio operations are unavailable while transcoding is in progress"}), 409

    output_dir = config.get('audio_tracks_directory', 'audio-tracks')
    socketio.start_background_task(
        target=extract_audio_track,
        socketio=socketio,
        file_path=file_path,
        track_index=int(track_index),
        track_meta=track_meta,
        output_dir=output_dir,
        user_id=session.get('user_id')
    )
    return jsonify({"status": "started"}), 202


@app.route('/audio/remove', methods=['POST'])
@login_required
def audio_remove():
    data = request.json
    file_path = data.get('path')
    track_index = data.get('track_index')

    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 400
    if track_index is None:
        return jsonify({"error": "track_index is required"}), 400
    if is_file_transcoding(file_path):
        return jsonify({"error": "Audio operations are unavailable while transcoding is in progress"}), 409

    socketio.start_background_task(
        target=remove_audio_track,
        socketio=socketio,
        file_path=file_path,
        track_index=int(track_index),
        user_id=session.get('user_id')
    )
    return jsonify({"status": "started"}), 202


@app.route('/audio/add', methods=['POST'])
@login_required
def audio_add():
    data = request.json
    file_path = data.get('path')
    audio_track_id = data.get('audio_track_id')

    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 400
    if not audio_track_id:
        return jsonify({"error": "audio_track_id is required"}), 400
    if is_file_transcoding(file_path):
        return jsonify({"error": "Audio operations are unavailable while transcoding is in progress"}), 409

    track = get_audio_track_by_id(audio_track_id)
    if not track or not os.path.exists(track['path']):
        return jsonify({"error": "Audio track not found"}), 404

    db_file = get_file_by_path(file_path)
    if not db_file:
        return jsonify({"error": "File not in database"}), 400

    media_info = json.loads(db_file['media_info']) if db_file['media_info'] else {}
    duration_str = media_info.get('container', {}).get('duration', '')
    import re
    m = re.match(r'([\d.]+)', duration_str)
    video_duration = float(m.group(1)) if m else None

    if not video_duration:
        return jsonify({"error": "Could not determine video duration"}), 400

    socketio.start_background_task(
        target=add_audio_track,
        socketio=socketio,
        file_path=file_path,
        audio_track_path=track['path'],
        video_duration=video_duration,
        track_title=track.get('title') or '',
        user_id=session.get('user_id')
    )
    return jsonify({"status": "started"}), 202


@app.route('/audio/tracks', methods=['GET'])
@login_required
def audio_tracks_list():
    return jsonify(get_all_audio_tracks())


@app.route('/audio/tracks/<int:track_id>', methods=['DELETE'])
@login_required
def audio_track_delete(track_id):
    track = get_audio_track_by_id(track_id)
    if not track:
        return jsonify({"error": "Track not found"}), 404

    if os.path.exists(track['path']):
        os.remove(track['path'])
    delete_audio_track(track_id)
    return jsonify({"status": "deleted"})


@app.route('/notifications', methods=['GET'])
@login_required
def notifications_list():
    user_id = session.get('user_id')
    items = get_notifications(user_id=user_id)
    count = get_unread_count(user_id=user_id)
    return jsonify({'items': items, 'unread_count': count})


@app.route('/notifications/unread-count', methods=['GET'])
@login_required
def notifications_unread_count():
    user_id = session.get('user_id')
    return jsonify({'count': get_unread_count(user_id=user_id)})


@app.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def notification_mark_read(notif_id):
    mark_notification_read(notif_id)
    return jsonify({'status': 'ok'})


@app.route('/notifications/read-all', methods=['POST'])
@login_required
def notifications_read_all():
    mark_all_notifications_read(user_id=session.get('user_id'))
    return jsonify({'status': 'ok'})


@app.route('/notifications/<int:notif_id>', methods=['DELETE'])
@login_required
def notification_delete(notif_id):
    delete_notification(notif_id)
    return jsonify({'status': 'ok'})


@app.route('/notifications', methods=['DELETE'])
@login_required
def notifications_delete_all():
    delete_all_notifications(user_id=session.get('user_id'))
    return jsonify({'status': 'ok'})


@app.route('/stats', methods=['GET'])
@login_required
def stats():
    return jsonify(get_app_stats() or {})


@app.route('/configure', methods=['GET'])
@login_required
def configure():
    return render_template('configure.html')


@app.route('/configure/data', methods=['GET'])
@login_required
def configure_data():
    return jsonify(config)


@app.route('/configure/save', methods=['POST'])
@login_required
def configure_save():
    data = request.json
    directories = [d for d in data.get('directories', []) if d.strip()]
    allowed_formats = [f.strip() for f in data.get('allowed_formats', '').split(',') if f.strip()]
    audio_tracks_directory = data.get('audio_tracks_directory', '').strip()
    transcoded_directory = data.get('transcoded_directory', '').strip()

    config['directories'] = directories
    config['allowed_formats'] = allowed_formats
    if audio_tracks_directory:
        config['audio_tracks_directory'] = audio_tracks_directory
    if transcoded_directory:
        config['transcoded_directory'] = transcoded_directory
    save_config(CONFIG_FILE, config)
    return jsonify({"status": "success"})


@socketio.on('connect')
def handle_connect():
    if 'user_id' not in session:
        return False  # reject unauthorized connections


if __name__ == '__main__':
    host  = os.environ.get('MCTL_HOST', '127.0.0.1')
    port  = int(os.environ.get('MCTL_PORT', 5000))
    debug = os.environ.get('MCTL_DEBUG', 'false').lower() == 'true'
    socketio.run(app, host=host, port=port, debug=debug)

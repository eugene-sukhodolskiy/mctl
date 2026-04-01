import os
import json
from flask import Blueprint, request, jsonify, session, send_from_directory
from urllib.parse import unquote
from server.db import (get_file_by_path, create_operation, get_file_operations,
                       get_operation_by_id, get_file_path_by_id, update_file_media_info,
                       mark_backup_deleted, get_file_backup_paths, delete_file_record,
                       get_connection, rename_file_record)
from server.mediascan import get_media_info_with_ffprobe
from server.thumbnails import get_or_generate_thumbs, invalidate_thumbs, get_thumbs_dir
from server.transcodate import transcode_file
from server.notifications import notify
from server.routes.auth import login_required
from server import state
from server.utils import check_writable, check_dir_writable

bp = Blueprint('transcoding', __name__)


def _restore_file_task(socketio, operation_id, backup_path, file_path, user_id=None):
    CHUNK_SIZE = 1024 * 1024
    tmp_path = file_path + '.restoring'
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
                socketio.emit('restore-progress', {'operation_id': operation_id, 'percent': percent})
                socketio.sleep(0)
        os.replace(tmp_path, file_path)
        if os.path.exists(backup_path):
            os.remove(backup_path)
        mark_backup_deleted(operation_id)
        fresh_info = get_media_info_with_ffprobe(file_path)
        if fresh_info:
            update_file_media_info(file_path, os.path.getsize(file_path), fresh_info)
        notify(socketio, user_id, 'success', f'Original restored: {os.path.basename(file_path)}')
        socketio.emit('restore-completed', {'operation_id': operation_id, 'file': file_path})
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        notify(socketio, user_id, 'error', f'Restore failed: {os.path.basename(file_path)}', str(e))
        socketio.emit('restore-error', {'operation_id': operation_id, 'message': str(e)})


@bp.route('/process-media', methods=['POST'])
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
    if codec == 'libaom-av1':
        cpu_used = data.get('preset-av1')

    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': 'File path is invalid or file does not exist'}), 400
    if state.is_file_transcoding(file_path):
        return jsonify({'error': 'File is already being transcoded'}), 409

    err = check_writable(file_path)
    if err:
        return jsonify({'error': err}), 403

    if delete_original:
        dest_path = None
    else:
        dest_dir = state.config.get('transcoded_directory', 'transcoded_files')
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, os.path.basename(file_path))
        err = check_dir_writable(dest_dir)
        if err:
            return jsonify({'error': err}), 403

    operation_id = None
    file_id = None
    db_file = get_file_by_path(file_path)
    if db_file:
        file_id = db_file['id']
        snapshot = json.loads(db_file['media_info']) if db_file['media_info'] else None
        operation_id = create_operation(
            file_id=db_file['id'],
            op_type='transcoding',
            params={'codec': codec, 'resolution': resolution, 'crf': crf,
                    'preset': preset, 'acceleration': acceleration,
                    'original_size_bytes': db_file['size_bytes']},
            snapshot_before=snapshot,
            backup_path=dest_path
        )

    state.socketio.start_background_task(
        target=transcode_file,
        transcoding_tasks=state.transcoding_tasks,
        socketio=state.socketio,
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
        user_id=session.get('user_id'),
        file_id=file_id
    )
    return jsonify({'status': 'processing started', 'file': file_path}), 202


@bp.route('/stop-transcoding', methods=['GET'])
@login_required
def stop_transcoding():
    task_id = request.args.get('task_id')
    if task_id in state.transcoding_tasks:
        task = state.transcoding_tasks.pop(task_id, None)
        if task:
            task['process'].terminate()
        return jsonify({'status': 'stopped', 'task_id': task_id})
    return jsonify({'status': 'error', 'message': 'Task not found'}), 404


@bp.route('/thumbnails/<int:file_id>', methods=['GET'])
@login_required
def thumbnails(file_id):
    with get_connection() as conn:
        row = conn.execute('SELECT path, media_info FROM files WHERE id = ?', (file_id,)).fetchone()
    if not row:
        return jsonify({'error': 'File not found'}), 404
    paths = get_or_generate_thumbs(file_id, row['path'], row['media_info'])
    urls = [f'/thumbs/{file_id}/{os.path.basename(p)}' for p in paths]
    return jsonify(urls)


@bp.route('/thumbs/<int:file_id>/<filename>')
@login_required
def serve_thumb(file_id, filename):
    return send_from_directory(os.path.abspath(get_thumbs_dir(file_id)), filename)


@bp.route('/file-history', methods=['GET'])
@login_required
def file_history():
    path = unquote(request.args.get('path', ''))
    if not path:
        return jsonify({'error': 'Path not provided'}), 400
    operations = get_file_operations(path)
    for op in operations:
        if op.get('params'):
            op['params'] = json.loads(op['params'])
        if op.get('snapshot_before'):
            op['snapshot_before'] = json.loads(op['snapshot_before'])
    return jsonify(operations)


@bp.route('/restore-original', methods=['POST'])
@login_required
def restore_original():
    operation_id = request.json.get('operation_id')
    if not operation_id:
        return jsonify({'error': 'operation_id is required'}), 400
    op = get_operation_by_id(operation_id)
    if not op:
        return jsonify({'error': 'Operation not found'}), 404
    backup_path = op.get('backup_path')
    if not backup_path or not os.path.exists(backup_path):
        return jsonify({'error': 'Backup file not found'}), 404
    file_path = get_file_path_by_id(op['file_id'])
    if not file_path:
        return jsonify({'error': 'Original file record not found'}), 404
    err = check_writable(backup_path)
    if err:
        return jsonify({'error': err}), 403
    if os.path.exists(file_path):
        err = check_writable(file_path)
        if err:
            return jsonify({'error': err}), 403
    state.socketio.start_background_task(
        target=_restore_file_task,
        socketio=state.socketio,
        operation_id=operation_id,
        backup_path=backup_path,
        file_path=file_path,
        user_id=session.get('user_id')
    )
    return jsonify({'status': 'restore started'}), 202


@bp.route('/delete-file', methods=['POST'])
@login_required
def delete_file():
    file_path = request.json.get('path')
    if not file_path:
        return jsonify({'error': 'path is required'}), 400
    if state.is_file_transcoding(file_path):
        return jsonify({'error': 'Cannot delete file while transcoding is in progress'}), 409
    if os.path.exists(file_path):
        err = check_writable(file_path)
        if err:
            return jsonify({'error': err}), 403
    db_file = get_file_by_path(file_path)
    if not db_file:
        return jsonify({'error': 'File not found in database'}), 404
    file_id = db_file['id']
    for backup_path in get_file_backup_paths(file_id):
        if os.path.exists(backup_path):
            os.remove(backup_path)
    invalidate_thumbs(file_id)
    if os.path.exists(file_path):
        os.remove(file_path)
    delete_file_record(file_id)
    return jsonify({'status': 'deleted'})


@bp.route('/delete-backup', methods=['POST'])
@login_required
def delete_backup():
    data = request.json
    operation_id = data.get('operation_id')
    direct_path = data.get('backup_path')
    if operation_id:
        op = get_operation_by_id(operation_id)
        if not op:
            return jsonify({'error': 'Operation not found'}), 404
        backup_path = op.get('backup_path')
        if not backup_path or not os.path.exists(backup_path):
            return jsonify({'error': 'Backup file not found'}), 404
        err = check_writable(backup_path)
        if err:
            return jsonify({'error': err}), 403
        os.remove(backup_path)
        mark_backup_deleted(operation_id)
    elif direct_path:
        if not os.path.exists(direct_path):
            return jsonify({'error': 'Backup file not found'}), 404
        err = check_writable(direct_path)
        if err:
            return jsonify({'error': err}), 403
        os.remove(direct_path)
    else:
        return jsonify({'error': 'operation_id or backup_path is required'}), 400
    return jsonify({'status': 'deleted'})


@bp.route('/rename-file', methods=['POST'])
@login_required
def rename_file():
    data = request.json
    old_path = data.get('path')
    new_name = (data.get('name') or '').strip()

    if not old_path or not new_name:
        return jsonify({'error': 'path and name are required'}), 400
    if not os.path.exists(old_path):
        return jsonify({'error': 'File not found'}), 404
    if state.is_file_transcoding(old_path):
        return jsonify({'error': 'Cannot rename file while transcoding is in progress'}), 409

    old_ext = os.path.splitext(old_path)[1]
    new_ext = os.path.splitext(new_name)[1]
    if not new_ext:
        new_name = new_name + old_ext
    elif new_ext.lower() != old_ext.lower():
        return jsonify({'error': f'Extension must remain {old_ext}'}), 400

    new_path = os.path.join(os.path.dirname(old_path), new_name)
    if os.path.exists(new_path):
        return jsonify({'error': 'A file with that name already exists'}), 409

    err = check_writable(old_path)
    if err:
        return jsonify({'error': err}), 403

    os.rename(old_path, new_path)
    rename_file_record(old_path, new_path, new_name)
    return jsonify({'status': 'renamed', 'new_path': new_path, 'new_name': new_name})

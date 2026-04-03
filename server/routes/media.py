import os
from flask import Blueprint, render_template, request, jsonify
from server.mediascan import scan_medialib, get_single_media_by_id, get_media_from_db
from server.db import get_latest_operation_by_backup_path
from server.routes.auth import login_required
from server import state

bp = Blueprint('media', __name__)


@bp.route('/')
@login_required
def index():
    return render_template('index.html')


@bp.route('/audio-tracks')
@login_required
def audio_tracks_page():
    return render_template('audio-tracks.html')


@bp.route('/originals')
@login_required
def originals_page():
    return render_template('originals.html')


@bp.route('/originals/list', methods=['GET'])
@login_required
def originals_list():
    backup_dir = state.config.get('transcoded_directory', 'transcoded_files')
    if not os.path.isdir(backup_dir):
        return jsonify([])

    result = []
    for fname in sorted(os.listdir(backup_dir)):
        fpath = os.path.join(backup_dir, fname)
        if not os.path.isfile(fpath):
            continue
        rec = get_latest_operation_by_backup_path(fpath) or {}
        result.append({
            'operation_id': rec.get('operation_id'),
            'backup_path':  fpath,
            'backup_name':  fname,
            'size_bytes':   os.path.getsize(fpath),
            'started_at':   rec.get('started_at'),
            'source_id':    rec.get('file_id'),
            'source_name':  rec.get('source_name'),
            'source_path':  rec.get('source_path'),
        })

    result.sort(key=lambda x: x.get('started_at') or '', reverse=True)
    return jsonify(result)


@bp.route('/single')
@login_required
def single_media():
    file_id = request.args.get('id', type=int)
    if not file_id:
        return 'id is required', 400
    media_file = get_single_media_by_id(file_id)
    if media_file is None:
        return 'File not found', 404
    return render_template('single.html', file=media_file, accelerators=state.available_accelerators)


@bp.route('/single-json')
@login_required
def single_media_json():
    file_id = request.args.get('id', type=int)
    if not file_id:
        return 'id is required', 400
    media_file = get_single_media_by_id(file_id)
    if media_file is None:
        return jsonify({'error': 'File not found'}), 404
    return jsonify(media_file)


@bp.route('/scan-status')
@login_required
def scan_status():
    return jsonify({'scanning': state.GStorage.get('scaning_state') == 'inprogress'})


@bp.route('/file-status')
@login_required
def file_status():
    path = request.args.get('path', '')
    return jsonify({'transcoding': state.is_file_transcoding(path)})


@bp.route('/media-list/clear-cache')
@login_required
def media_list_clear_cache():
    if state.GStorage['scaning_state'] == 'inprogress':
        return jsonify({'status': True})
    scan_medialib(state.config, state.GStorage, state.socketio)
    return jsonify({'status': True})


@bp.route('/media-list', methods=['GET'])
@login_required
def media_list():
    files = get_media_from_db() or []
    if state.GStorage['scaning_state'] == 'inprogress':
        return jsonify({'status': 'scaning', 'data': files})
    return jsonify({'status': True, 'data': files})

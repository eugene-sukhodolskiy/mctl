import os
import json
import re
from flask import Blueprint, request, jsonify, session
from server.audio import extract_audio_track, remove_audio_track, add_audio_track
from server.db import get_file_by_path, get_audio_track_by_id, get_all_audio_tracks, delete_audio_track
from server.routes.auth import login_required
from server import state
from server.utils import check_writable, check_dir_writable

bp = Blueprint('audio_routes', __name__, url_prefix='/audio')


@bp.route('/extract', methods=['POST'])
@login_required
def audio_extract():
    data = request.json
    file_path = data.get('path')
    track_index = data.get('track_index')
    track_meta = data.get('track_meta', {})

    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 400
    if track_index is None:
        return jsonify({'error': 'track_index is required'}), 400
    if state.is_file_transcoding(file_path):
        return jsonify({'error': 'Audio operations are unavailable while transcoding is in progress'}), 409

    output_dir = state.config.get('audio_tracks_directory', 'audio-tracks')
    os.makedirs(output_dir, exist_ok=True)
    err = check_dir_writable(output_dir)
    if err:
        return jsonify({'error': err}), 403

    state.socketio.start_background_task(
        target=extract_audio_track,
        socketio=state.socketio,
        file_path=file_path,
        track_index=int(track_index),
        track_meta=track_meta,
        output_dir=output_dir,
        user_id=session.get('user_id')
    )
    return jsonify({'status': 'started'}), 202


@bp.route('/remove', methods=['POST'])
@login_required
def audio_remove():
    data = request.json
    file_path = data.get('path')
    track_index = data.get('track_index')

    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 400
    if track_index is None:
        return jsonify({'error': 'track_index is required'}), 400
    if state.is_file_transcoding(file_path):
        return jsonify({'error': 'Audio operations are unavailable while transcoding is in progress'}), 409

    err = check_writable(file_path)
    if err:
        return jsonify({'error': err}), 403

    state.socketio.start_background_task(
        target=remove_audio_track,
        socketio=state.socketio,
        file_path=file_path,
        track_index=int(track_index),
        user_id=session.get('user_id')
    )
    return jsonify({'status': 'started'}), 202


@bp.route('/add', methods=['POST'])
@login_required
def audio_add():
    data = request.json
    file_path = data.get('path')
    audio_track_id = data.get('audio_track_id')

    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 400
    if not audio_track_id:
        return jsonify({'error': 'audio_track_id is required'}), 400
    if state.is_file_transcoding(file_path):
        return jsonify({'error': 'Audio operations are unavailable while transcoding is in progress'}), 409

    err = check_writable(file_path)
    if err:
        return jsonify({'error': err}), 403

    track = get_audio_track_by_id(audio_track_id)
    if not track or not os.path.exists(track['path']):
        return jsonify({'error': 'Audio track not found'}), 404

    db_file = get_file_by_path(file_path)
    if not db_file:
        return jsonify({'error': 'File not in database'}), 400

    media_info = json.loads(db_file['media_info']) if db_file['media_info'] else {}
    duration_str = media_info.get('container', {}).get('duration', '')
    m = re.match(r'([\d.]+)', duration_str)
    video_duration = float(m.group(1)) if m else None

    if not video_duration:
        return jsonify({'error': 'Could not determine video duration'}), 400

    state.socketio.start_background_task(
        target=add_audio_track,
        socketio=state.socketio,
        file_path=file_path,
        audio_track_path=track['path'],
        video_duration=video_duration,
        track_title=track.get('title') or '',
        user_id=session.get('user_id')
    )
    return jsonify({'status': 'started'}), 202


@bp.route('/tracks', methods=['GET'])
@login_required
def audio_tracks_list():
    return jsonify(get_all_audio_tracks())


@bp.route('/tracks/<int:track_id>', methods=['DELETE'])
@login_required
def audio_track_delete(track_id):
    track = get_audio_track_by_id(track_id)
    if not track:
        return jsonify({'error': 'Track not found'}), 404
    if os.path.exists(track['path']):
        err = check_writable(track['path'])
        if err:
            return jsonify({'error': err}), 403
        os.remove(track['path'])
    delete_audio_track(track_id)
    return jsonify({'status': 'deleted'})

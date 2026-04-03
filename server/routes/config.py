from flask import Blueprint, render_template, request, jsonify
from server.mediascan import save_config
from server.db import get_app_stats
from server.routes.auth import login_required
from server import state

bp = Blueprint('config', __name__)


@bp.route('/stats', methods=['GET'])
@login_required
def stats():
    return jsonify(get_app_stats() or {})


@bp.route('/configure', methods=['GET'])
@login_required
def configure():
    return render_template('configure.html')


@bp.route('/configure/data', methods=['GET'])
@login_required
def configure_data():
    return jsonify(state.config)


@bp.route('/configure/save', methods=['POST'])
@login_required
def configure_save():
    data = request.json
    directories = [d for d in data.get('directories', []) if d.strip()]
    allowed_formats = [f.strip() for f in data.get('allowed_formats', '').split(',') if f.strip()]
    audio_tracks_directory = data.get('audio_tracks_directory', '').strip()
    transcoded_directory = data.get('transcoded_directory', '').strip()

    state.config['directories'] = directories
    state.config['allowed_formats'] = allowed_formats
    if audio_tracks_directory:
        state.config['audio_tracks_directory'] = audio_tracks_directory
    if transcoded_directory:
        state.config['transcoded_directory'] = transcoded_directory
    save_config(state.CONFIG_FILE, state.config)
    return jsonify({'status': 'success'})

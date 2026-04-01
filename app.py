from gevent import monkey
monkey.patch_all()

import os
from flask import Flask, session
from flask_socketio import SocketIO
from server import state
from server.mediascan import load_config, save_config
from server.transcodate import detect_available_accelerators
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

CONFIG_FILE = os.environ.get('MCTL_CONFIG', 'data/config.json')

app = Flask(__name__)

config = load_config(CONFIG_FILE)
if not config.get('secret_key'):
    config['secret_key'] = os.urandom(32).hex()
    save_config(CONFIG_FILE, config)
app.secret_key = config['secret_key']

socketio = SocketIO(app)

state.config = config
state.CONFIG_FILE = CONFIG_FILE
state.socketio = socketio
state.available_accelerators = detect_available_accelerators()

alembic_cfg = AlembicConfig('alembic.ini')
alembic_command.upgrade(alembic_cfg, 'head')

from server.routes.auth import bp as auth_bp
from server.routes.media import bp as media_bp
from server.routes.transcoding import bp as transcoding_bp
from server.routes.audio import bp as audio_bp
from server.routes.notifications import bp as notifications_bp
from server.routes.config import bp as config_bp

app.register_blueprint(auth_bp)
app.register_blueprint(media_bp)
app.register_blueprint(transcoding_bp)
app.register_blueprint(audio_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(config_bp)


@socketio.on('connect')
def handle_connect():
    if 'user_id' not in session:
        return False


if __name__ == '__main__':
    host = os.environ.get('MCTL_HOST', '127.0.0.1')
    port = int(os.environ.get('MCTL_PORT', 5000))
    debug = os.environ.get('MCTL_DEBUG', 'false').lower() == 'true'
    socketio.run(app, host=host, port=port, debug=debug)

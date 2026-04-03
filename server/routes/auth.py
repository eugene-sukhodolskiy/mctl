from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from server.db import get_users_count, create_user, get_user_by_username, update_user_password, get_connection
from server.mediascan import save_config
from server import state

bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if get_users_count() == 0:
        return redirect(url_for('auth.register'))
    if 'user_id' in session:
        return redirect(url_for('media.index'))
    if request.method == 'POST':
        data = request.json
        user = get_user_by_username(data.get('username', ''))
        if user and check_password_hash(user['password_hash'], data.get('password', '')):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return jsonify({'status': 'ok'})
        return jsonify({'error': 'Invalid username or password'}), 401
    return render_template('login.html')


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if get_users_count() > 0:
        return redirect(url_for('auth.login'))
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


@bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if not state.config.get('reset_admin_password'):
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        data = request.json
        password = data.get('password', '')
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        with get_connection() as conn:
            row = conn.execute('SELECT id FROM users WHERE is_superadmin = 1 ORDER BY id LIMIT 1').fetchone()
        if not row:
            return jsonify({'error': 'No superadmin found'}), 404
        update_user_password(row['id'], generate_password_hash(password))
        state.config.pop('reset_admin_password', None)
        save_config(state.CONFIG_FILE, state.config)
        return jsonify({'status': 'ok'})
    return render_template('reset-password.html')

from flask import Blueprint, request, jsonify, session
from server.db import (get_notifications, get_unread_count, mark_notification_read,
                       mark_all_notifications_read, delete_notification, delete_all_notifications)
from server.routes.auth import login_required

bp = Blueprint('notifications', __name__, url_prefix='/notifications')


@bp.route('', methods=['GET'])
@login_required
def notifications_list():
    user_id = session.get('user_id')
    return jsonify({'items': get_notifications(user_id=user_id), 'unread_count': get_unread_count(user_id=user_id)})


@bp.route('/unread-count', methods=['GET'])
@login_required
def notifications_unread_count():
    return jsonify({'count': get_unread_count(user_id=session.get('user_id'))})


@bp.route('/<int:notif_id>/read', methods=['POST'])
@login_required
def notification_mark_read(notif_id):
    mark_notification_read(notif_id)
    return jsonify({'status': 'ok'})


@bp.route('/read-all', methods=['POST'])
@login_required
def notifications_read_all():
    mark_all_notifications_read(user_id=session.get('user_id'))
    return jsonify({'status': 'ok'})


@bp.route('/<int:notif_id>', methods=['DELETE'])
@login_required
def notification_delete(notif_id):
    delete_notification(notif_id)
    return jsonify({'status': 'ok'})


@bp.route('', methods=['DELETE'])
@login_required
def notifications_delete_all():
    delete_all_notifications(user_id=session.get('user_id'))
    return jsonify({'status': 'ok'})

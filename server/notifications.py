from datetime import datetime
from .db import create_notification


def notify(socketio, user_id, notif_type, title, message=None):
    """Create a persistent notification and push it to connected clients via SocketIO."""
    notif_id = create_notification(user_id, notif_type, title, message)
    socketio.emit('notification', {
        'id': notif_id,
        'user_id': user_id,
        'type': notif_type,
        'title': title,
        'message': message,
        'is_read': False,
        'created_at': datetime.utcnow().isoformat()
    })

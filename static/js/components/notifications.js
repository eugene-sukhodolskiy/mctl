// Notification center + toast system

let _notifUnreadCount = 0;
const _notifChannel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('mctl_notif_badge') : null;

if (_notifChannel) {
    _notifChannel.onmessage = (e) => {
        if (e.data.type === 'badge') _setBadge(e.data.count, false);
    };
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function _timeAgo(isoStr) {
    const diff = Math.floor((Date.now() - new Date(isoStr + 'Z').getTime()) / 1000);
    if (diff < 60)    return 'just now';
    if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
}

function _notifIcon(type) {
    return {
        success: 'bi-check-circle',
        error:   'bi-exclamation-triangle',
        warning: 'bi-exclamation-circle',
        info:    'bi-info-circle'
    }[type] || 'bi-bell';
}

function _notifColor(type) {
    return {
        success: 'var(--tn-green)',
        error:   'var(--tn-red)',
        warning: 'var(--tn-yellow)',
        info:    'var(--tn-blue)'
    }[type] || 'var(--tn-blue)';
}

// ─── Badge ────────────────────────────────────────────────────────────────────

function _setBadge(count, broadcast = true) {
    _notifUnreadCount = Math.max(0, count);
    const badge = document.querySelector('.open-notifications .notif-badge');
    if (badge) badge.textContent = _notifUnreadCount > 0 ? (_notifUnreadCount > 99 ? '99+' : _notifUnreadCount) : '';
    if (broadcast && _notifChannel) _notifChannel.postMessage({ type: 'badge', count: _notifUnreadCount });
}

function _adjustBadge(delta) {
    _setBadge(_notifUnreadCount + delta);
}

// ─── Toast ────────────────────────────────────────────────────────────────────

function pushNotificationToast(notif) {
    const icon  = _notifIcon(notif.type);
    const color = _notifColor(notif.type);
    const msgHtml = notif.message
        ? `<div class="notif-toast-msg">${notif.message.replace(/</g,'&lt;').replace(/\n/g,'<br>')}</div>`
        : '';

    const el = document.createElement('div');
    el.className = 'notif-toast shadow';
    el.style.setProperty('--notif-color', color);
    el.innerHTML = `
        <div class="notif-toast-header">
            <i class="bi ${icon} notif-toast-icon"></i>
            <span class="notif-toast-title">${notif.title.replace(/</g,'&lt;')}</span>
            <button type="button" class="btn-close ms-auto" aria-label="Close"></button>
        </div>
        ${msgHtml}
    `;

    let hovered = false;
    let markedRead = false;
    let autoTimer = null;

    function markRead() {
        if (markedRead || !notif.id) return;
        markedRead = true;
        $.post(`/notifications/${notif.id}/read`);
        _adjustBadge(-1);
    }

    function hide() {
        el.classList.remove('show');
        setTimeout(() => el.remove(), 300);
    }

    function startTimer() {
        autoTimer = setTimeout(() => { if (!hovered) hide(); }, 5000);
    }

    el.addEventListener('mouseenter', () => {
        hovered = true;
        clearTimeout(autoTimer);
        markRead();
    });
    el.addEventListener('mouseleave', () => {
        hovered = false;
        startTimer();
    });
    el.querySelector('.btn-close').addEventListener('click', () => {
        markRead();
        hide();
    });

    document.querySelector('.component.errors-center').appendChild(el);
    setTimeout(() => el.classList.add('show'), 50);
    startTimer();
}

// ─── Notification center panel ────────────────────────────────────────────────

function _buildNotifItem(notif) {
    const icon    = _notifIcon(notif.type);
    const color   = _notifColor(notif.type);
    const time    = _timeAgo(notif.created_at);
    const isRead  = notif.is_read;
    const MSG_THRESHOLD = 120;
    const longMsg = notif.message && notif.message.length > MSG_THRESHOLD;

    let msgHtml = '';
    if (notif.message) {
        const escaped = notif.message.replace(/</g, '&lt;').replace(/\n/g, '<br>');
        const preview = longMsg
            ? notif.message.slice(0, MSG_THRESHOLD).replace(/</g, '&lt;').replace(/\n/g, '<br>') + '…'
            : escaped;
        const expandBtn = longMsg ? `<button class="notif-expand-btn">show more</button>` : '';
        msgHtml = `<div class="notif-item-msg${longMsg ? ' collapsed' : ''}" data-full="${escaped.replace(/"/g,'&quot;')}" data-preview="${preview.replace(/"/g,'&quot;')}">${preview}</div>${expandBtn}`;
    }

    const el = document.createElement('div');
    el.className = `notif-item ${isRead ? 'is-read' : 'is-unread'}`;
    el.dataset.id = notif.id;
    el.style.setProperty('--notif-color', color);
    el.innerHTML = `<div class="notif-item-header"><i class="bi ${icon} notif-item-icon"></i><div class="notif-item-meta"><span class="notif-item-title">${notif.title.replace(/</g,'&lt;')}</span><span class="notif-item-time">${time}</span></div><button class="notif-delete-btn" title="delete"><i class="bi bi-x"></i></button></div>${msgHtml}`;

    if (longMsg) {
        el.querySelector('.notif-expand-btn').addEventListener('click', function() {
            const msgEl = el.querySelector('.notif-item-msg');
            const expanded = !msgEl.classList.contains('collapsed');
            if (expanded) {
                msgEl.classList.add('collapsed');
                msgEl.innerHTML = msgEl.dataset.preview;
                this.textContent = 'show more';
            } else {
                msgEl.classList.remove('collapsed');
                msgEl.innerHTML = msgEl.dataset.full;
                this.textContent = 'show less';
            }
        });
    }

    el.querySelector('.notif-delete-btn').addEventListener('click', () => {
        $.ajax({ url: `/notifications/${notif.id}`, method: 'DELETE' });
        el.classList.add('removing');
        setTimeout(() => el.remove(), 250);
        _checkEmpty();
    });

    return el;
}

function _checkEmpty() {
    setTimeout(() => {
        const list = document.getElementById('notif-list');
        const empty = document.getElementById('notif-empty');
        if (list && empty) {
            const hasItems = list.querySelectorAll('.notif-item').length > 0;
            empty.classList.toggle('d-none', hasItems);
        }
    }, 300);
}

function loadNotifications() {
    const list    = document.getElementById('notif-list');
    const empty   = document.getElementById('notif-empty');
    const loading = document.getElementById('notif-loading');
    if (!list) return;

    loading.classList.remove('d-none');
    list.innerHTML = '';
    empty.classList.add('d-none');

    $.getJSON('/notifications', function(data) {
        loading.classList.add('d-none');
        if (!data.items || data.items.length === 0) {
            empty.classList.remove('d-none');
            return;
        }
        data.items.forEach(n => list.appendChild(_buildNotifItem(n)));
    });
}

// ─── Init ─────────────────────────────────────────────────────────────────────

$(document).ready(function() {
    // Fetch initial unread count
    $.getJSON('/notifications/unread-count', function(data) {
        _setBadge(data.count || 0);
    });

    // Open panel → load + mark all read
    const offcanvasEl = document.getElementById('notifications-center');
    if (offcanvasEl) {
        offcanvasEl.addEventListener('show.bs.offcanvas', () => {
            loadNotifications();
        });
        offcanvasEl.addEventListener('shown.bs.offcanvas', () => {
            $.post('/notifications/read-all', function() {
                _setBadge(0);
                offcanvasEl.querySelectorAll('.notif-item.is-unread').forEach(el => {
                    el.classList.remove('is-unread');
                    el.classList.add('is-read');
                });
            });
        });
    }

    // Mark all read button
    $('#notif-mark-all-read').on('click', function() {
        $.post('/notifications/read-all', function() {
            _setBadge(0);
            document.querySelectorAll('#notif-list .notif-item').forEach(el => {
                el.classList.remove('is-unread');
                el.classList.add('is-read');
            });
        });
    });

    // Clear all button
    $('#notif-clear-all').on('click', function() {
        $.ajax({ url: '/notifications', method: 'DELETE', success: function() {
            document.getElementById('notif-list').innerHTML = '';
            _setBadge(0);
            _checkEmpty();
        }});
    });

    // SocketIO: incoming notification
    if (typeof socket !== 'undefined') {
        socket.on('notification', function(notif) {
            _adjustBadge(1);
            pushNotificationToast(notif);
        });
    }
});

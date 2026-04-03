function pushErrMsg(msg) {
    pushNotificationToast({ type: 'error', title: msg });
}

function pushInfoMsg(msg) {
    pushNotificationToast({ type: 'info', title: msg });
}

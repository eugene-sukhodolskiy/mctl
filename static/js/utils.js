function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return "0 B";
    if (bytes >= 1099511627776) return (bytes / 1099511627776).toFixed(2) + " TB";
    if (bytes >= 1073741824)    return (bytes / 1073741824).toFixed(2) + " GB";
    if (bytes >= 1048576)       return (bytes / 1048576).toFixed(1) + " MB";
    return (bytes / 1024).toFixed(0) + " KB";
}

function timeToSeconds(timeStr) {
    let parts = timeStr.split(':');
    let hours = parseInt(parts[0], 10);
    let minutes = parseInt(parts[1], 10);
    let seconds = parseFloat(parts[2]);

    return hours * 3600 + minutes * 60 + seconds;
}
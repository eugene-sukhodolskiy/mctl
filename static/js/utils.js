function timeToSeconds(timeStr) {
    let parts = timeStr.split(':');
    let hours = parseInt(parts[0], 10);
    let minutes = parseInt(parts[1], 10);
    let seconds = parseFloat(parts[2]);

    return hours * 3600 + minutes * 60 + seconds;
}
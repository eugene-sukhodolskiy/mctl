function renderFooterStats(s) {
    if (!s || !s.transcoded_count) return;
    $("#stat-count").text(s.transcoded_count);
    $("#stat-saved").text(formatBytes(s.saved_bytes));
    $("#stat-percent").text(s.percent_saved + "%");
    $("#footer-stats").show();
}

$(document).ready(function() {
    $.getJSON("/stats", function(s) { renderFooterStats(s); });

    socket.on("completed", function(data) {
        if (data.stats) renderFooterStats(data.stats);
    });
});

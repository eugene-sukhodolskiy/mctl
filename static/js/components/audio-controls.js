function audioControlsInit() {
    const filePath = mediaInfo.path;

    // Transcoding lock
    let transcodingLocked = false;

    function warnTranscodingLocked() {
        pushInfoMsg("Audio operations are unavailable while transcoding is in progress.");
    }

    $.getJSON("/file-status?path=" + encodeURIComponent(filePath), function(data) {
        transcodingLocked = data.transcoding;
    });

    socket.on("progress", function(data) {
        if (data.task.file === filePath) transcodingLocked = true;
    });
    socket.on("copy-progress", function(data) {
        if (data.file === filePath) transcodingLocked = true;
    });
    socket.on("completed", function(data) {
        if (data.task.file === filePath) transcodingLocked = false;
    });
    socket.on("error", function(data) {
        if (data.task.file === filePath) transcodingLocked = false;
    });
    socket.on("canceled", function(data) {
        if (data.task.file === filePath) transcodingLocked = false;
    });

    // Extract audio track
    $(".btn-extract-audio").on("click", function() {
        if (transcodingLocked) { warnTranscodingLocked(); return; }
        const btn = $(this);
        const row = btn.closest("tr");
        btn.prop("disabled", true).find(".spinner-border").show();
        btn.find("i").hide();

        const trackMeta = {
            codec:    row.data("track-codec"),
            title:    row.data("track-title"),
            language: row.data("track-language"),
            bitrate:  row.data("track-bitrate"),
            channels: row.data("track-channels")
        };

        $.ajax({
            url: "/audio/extract",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                path: filePath,
                track_index: row.data("track-index"),
                track_meta: trackMeta
            }),
            error: function(xhr) {
                btn.prop("disabled", false).find(".spinner-border").hide();
                btn.find("i").show();
                pushErrMsg("Extract failed: " + (xhr.responseJSON?.error || "unknown error"));
            }
        });
    });

    socket.on("audio-extract-completed", function(data) {
        if (data.file !== filePath) return;
        const row = $(`tr[data-track-index="${data.track_index}"]`);
        const btn = row.find(".btn-extract-audio");
        btn.prop("disabled", false).find(".spinner-border").hide();
        btn.find("i").show().removeClass("bi-box-arrow-up").addClass("bi-check-lg");
        btn.css("color", "var(--tn-green)");
        loadAudioTrackOptions();
    });

    socket.on("audio-extract-error", function(data) {
        if (data.file !== filePath) return;
        const row = $(`tr[data-track-index="${data.track_index}"]`);
        const btn = row.find(".btn-extract-audio");
        btn.prop("disabled", false).find(".spinner-border").hide();
        btn.find("i").show();
        pushErrMsg("Extract failed: " + data.message);
    });

    // Remove audio track
    let pendingRemoveRow = null;
    const removeModal = new bootstrap.Modal(document.getElementById("confirm-remove-audio"));

    $(".btn-remove-audio").on("click", function() {
        if (transcodingLocked) { warnTranscodingLocked(); return; }
        const row = $(this).closest("tr");
        const title = row.data("track-title") || row.data("track-language") || `track ${row.data("track-index")}`;
        pendingRemoveRow = row;
        $("#confirm-remove-track-name").text(title);
        removeModal.show();
    });

    $("#confirm-remove-audio-btn").on("click", function() {
        if (!pendingRemoveRow) return;
        const row = pendingRemoveRow;
        const confirmBtn = $(this);
        confirmBtn.prop("disabled", true).find(".spinner-border").show();

        row.find(".btn-remove-audio").prop("disabled", true);

        $.ajax({
            url: "/audio/remove",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                path: filePath,
                track_index: row.data("track-index")
            }),
            success: function() {
                removeModal.hide();
            },
            error: function(xhr) {
                confirmBtn.prop("disabled", false).find(".spinner-border").hide();
                row.find(".btn-remove-audio").prop("disabled", false);
                removeModal.hide();
                pushErrMsg("Remove failed: " + (xhr.responseJSON?.error || "unknown error"));
            }
        });
    });

    document.getElementById("confirm-remove-audio").addEventListener("hidden.bs.modal", function() {
        pendingRemoveRow = null;
        $("#confirm-remove-audio-btn").prop("disabled", false).find(".spinner-border").hide();
    });

    socket.on("audio-remove-completed", function(data) {
        if (data.file !== filePath) return;
        window.location.reload();
    });

    socket.on("audio-remove-error", function(data) {
        if (data.file !== filePath) return;
        const row = $(`tr[data-track-index="${data.track_index}"]`);
        row.find(".btn-remove-audio").prop("disabled", false);
        pushErrMsg("Remove failed: " + data.message);
    });

    // Add audio track panel
    $("#toggle-add-audio").on("click", function() {
        const body = $("#add-audio-body");
        const icon = $(this).find("i");
        if (body.is(":visible")) {
            body.slideUp();
            icon.removeClass("bi-chevron-up").addClass("bi-chevron-down");
        } else {
            body.slideDown();
            icon.removeClass("bi-chevron-down").addClass("bi-chevron-up");
            loadAudioTrackOptions();
        }
    });

    function loadAudioTrackOptions() {
        $.getJSON("/audio/tracks", function(tracks) {
            const select = $("#audio-track-select");
            const addBtn = $("#btn-add-audio");
            select.empty();
            if (!tracks.length) {
                select.append('<option value="">no extracted tracks available</option>');
                addBtn.prop("disabled", true);
                return;
            }
            select.append('<option value="">select a track...</option>');
            tracks.forEach(t => {
                const label = `${t.source_name} — ${t.language || "?"} [${t.codec || "?"}] ${t.title || ""}`.trim();
                select.append(`<option value="${t.id}">${label}</option>`);
            });
            addBtn.prop("disabled", false);
        });
    }

    $("#audio-track-select").on("change", function() {
        $("#btn-add-audio").prop("disabled", !$(this).val());
    });

    $("#btn-add-audio").on("click", function() {
        if (transcodingLocked) { warnTranscodingLocked(); return; }
        const trackId = $("#audio-track-select").val();
        if (!trackId) return;

        const btn = $(this);
        btn.prop("disabled", true).find(".spinner-border").show();

        $.ajax({
            url: "/audio/add",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({ path: filePath, audio_track_id: parseInt(trackId) }),
            error: function(xhr) {
                btn.prop("disabled", false).find(".spinner-border").hide();
                pushErrMsg("Add audio failed: " + (xhr.responseJSON?.error || "unknown error"));
            }
        });
    });

    socket.on("audio-add-completed", function(data) {
        if (data.file !== filePath) return;
        window.location.reload();
    });

    socket.on("audio-add-error", function(data) {
        if (data.file !== filePath) return;
        const btn = $("#btn-add-audio");
        btn.prop("disabled", false).find(".spinner-border").hide();
        pushErrMsg("Add audio failed: " + data.message);
    });
}

$(document).ready(function() {
    if (typeof mediaInfo !== "undefined") {
        audioControlsInit();
    }
});

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
        btn.prop("disabled", true);

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
                btn.prop("disabled", false);
                pushErrMsg("Extract failed: " + (xhr.responseJSON?.error || "unknown error"));
            }
        });
    });

    // Initialise all circle progress bars in the audio table
    $("tr[data-track-index] .circle-progress-bar").each(function() {
        initSingleCircleProgressBar(this);
    });
    initSingleCircleProgressBar(document.querySelector("#add-audio-progress .circle-progress-bar"));

    function getTrackRow(trackIndex) {
        return $(`tr[data-track-index="${trackIndex}"]`);
    }

    function showTrackProgress(trackIndex, percent) {
        const row = getTrackRow(trackIndex);
        const cpbar = row.find(".circle-progress-bar")[0];
        if (cpbar) cpbar.dataset.value = percent;
        row.find(".audio-op-percent").text(percent + "%");
        row.find(".audio-op-buttons").addClass("d-none");
        row.find(".audio-op-progress").removeClass("d-none").css("display", "flex");
    }

    function hideTrackProgress(trackIndex) {
        const row = getTrackRow(trackIndex);
        row.find(".audio-op-progress").addClass("d-none").css("display", "");
        row.find(".audio-op-buttons").removeClass("d-none");
    }

    socket.on("audio-extract-progress", function(data) {
        if (data.file !== filePath) return;
        showTrackProgress(data.track_index, data.percent);
    });

    socket.on("audio-extract-completed", function(data) {
        if (data.file !== filePath) return;
        hideTrackProgress(data.track_index);
        const btn = getTrackRow(data.track_index).find(".btn-extract-audio");
        btn.prop("disabled", false);
        btn.find("i").show().removeClass("bi-box-arrow-up").addClass("bi-check-lg");
        btn.css("color", "var(--tn-green)");
        loadAudioTrackOptions();
    });

    socket.on("audio-extract-error", function(data) {
        if (data.file !== filePath) return;
        hideTrackProgress(data.track_index);
        getTrackRow(data.track_index).find(".btn-extract-audio").prop("disabled", false);
        pushErrMsg("Extract failed: " + data.message);
    });

    socket.on("audio-extract-canceled", function(data) {
        if (data.file !== filePath) return;
        hideTrackProgress(data.track_index);
        getTrackRow(data.track_index).find(".btn-extract-audio").prop("disabled", false);
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

    socket.on("audio-remove-progress", function(data) {
        if (data.file !== filePath) return;
        showTrackProgress(data.track_index, data.percent);
    });

    socket.on("audio-remove-completed", function(data) {
        if (data.file !== filePath) return;
        window.location.reload();
    });

    socket.on("audio-remove-error", function(data) {
        if (data.file !== filePath) return;
        hideTrackProgress(data.track_index);
        getTrackRow(data.track_index).find(".btn-remove-audio").prop("disabled", false);
        pushErrMsg("Remove failed: " + data.message);
    });

    socket.on("audio-remove-canceled", function(data) {
        if (data.file !== filePath) return;
        hideTrackProgress(data.track_index);
        getTrackRow(data.track_index).find(".btn-remove-audio").prop("disabled", false);
        $("#confirm-remove-audio-btn").prop("disabled", false).find(".spinner-border").hide();
        removeModal.hide();
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

    socket.on("audio-add-progress", function(data) {
        if (data.file !== filePath) return;
        const pct = data.percent;
        const cpbar = document.querySelector("#add-audio-progress .circle-progress-bar");
        if (cpbar) cpbar.dataset.value = pct;
        $("#add-audio-progress-label").text(pct + "%");
        $("#add-audio-progress").removeClass("d-none").css("display", "flex");
    });

    socket.on("audio-add-completed", function(data) {
        if (data.file !== filePath) return;
        window.location.reload();
    });

    socket.on("audio-add-error", function(data) {
        if (data.file !== filePath) return;
        $("#add-audio-progress").addClass("d-none").css("display", "");
        $("#btn-add-audio").prop("disabled", false);
        pushErrMsg("Add audio failed: " + data.message);
    });

    socket.on("audio-add-canceled", function(data) {
        if (data.file !== filePath) return;
        $("#add-audio-progress").addClass("d-none").css("display", "");
        $("#btn-add-audio").prop("disabled", false);
    });
}

$(document).ready(function() {
    if (typeof mediaInfo !== "undefined") {
        audioControlsInit();
    }
});

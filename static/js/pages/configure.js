function makeDirRow(value) {
    const row = $(`
        <div class="input-group dir-row">
            <input type="text" class="form-control dir-input" value="${value}" placeholder="/path/to/directory">
            <button class="btn btn-outline-secondary btn-remove-dir" type="button" title="remove">
                <i class="bi bi-dash-lg"></i>
            </button>
        </div>
    `);
    row.find(".btn-remove-dir").on("click", function() {
        row.remove();
    });
    return row;
}

$(document).ready(function() {
    $.getJSON("/configure/data", function(cfg) {
        const list = $("#directories-list");
        (cfg.directories || []).forEach(d => list.append(makeDirRow(d)));
        if (!cfg.directories || !cfg.directories.length) list.append(makeDirRow(''));

        $("#allowed-formats").val((cfg.allowed_formats || []).join(", "));
        $("#audio-tracks-directory").val(cfg.audio_tracks_directory || '');
        $("#transcoded-directory").val(cfg.transcoded_directory || '');
    });

    $("#btn-add-dir").on("click", function() {
        $("#directories-list").append(makeDirRow(''));
        $("#directories-list .dir-input").last().focus();
    });

    $("#btn-save").on("click", function() {
        const btn = $(this);
        btn.prop("disabled", true).find(".spinner-border").show();

        const directories = $(".dir-input").map(function() {
            return $(this).val().trim();
        }).get().filter(Boolean);

        const payload = {
            directories,
            allowed_formats: $("#allowed-formats").val(),
            audio_tracks_directory: $("#audio-tracks-directory").val().trim(),
            transcoded_directory: $("#transcoded-directory").val().trim(),
        };

        $.ajax({
            url: "/configure/save",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify(payload),
            success: function() {
                btn.prop("disabled", false).find(".spinner-border").hide();
                const status = $("#save-status");
                status.text("saved").css("color", "var(--tn-green)").show();
                setTimeout(() => status.fadeOut(), 2500);
            },
            error: function(xhr) {
                btn.prop("disabled", false).find(".spinner-border").hide();
                pushErrMsg("Save failed: " + (xhr.responseJSON?.error || "unknown error"));
            }
        });
    });
});

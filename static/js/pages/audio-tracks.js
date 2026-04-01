function loadAudioTracks() {
    $.getJSON("/audio/tracks", function(tracks) {
        const empty = $(".audio-tracks-empty");
        const table = $(".audio-tracks-table");
        const tbody = table.find("tbody");

        tbody.empty();
        if (!tracks.length) {
            empty.show(); table.hide();
            return;
        }

        empty.hide(); table.show();
        tracks.forEach(t => {
            const date = t.created_at
                ? new Date(t.created_at).toLocaleString()
                : "—";
            const filename = t.path.split("/").at(-1);
            tbody.append(`
                <tr data-id="${t.id}">
                    <td><a href="/single?path=${encodeURIComponent(t.source_path)}">${t.source_name}</a></td>
                    <td>${t.language || "—"}</td>
                    <td>${t.codec || "—"}</td>
                    <td>${t.bitrate || "—"}</td>
                    <td>${t.channels || "—"}</td>
                    <td>${t.title || "—"}</td>
                    <td><small class="text-muted">${date}</small></td>
                    <td>
                        <button class="btn btn-outline-secondary btn-sm btn-delete-track" data-id="${t.id}">
                            <span class="spinner-border spinner-border-sm" style="display:none"></span>
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>
                </tr>
            `);
        });
    });
}

$(document).ready(function() {
    loadAudioTracks();

    let pendingDeleteId = null;
    const deleteModal = new bootstrap.Modal(document.getElementById("confirm-delete-track"));

    $(document).on("click", ".btn-delete-track", function() {
        const row = $(this).closest("tr");
        const filename = row.find("td:first a").text() || "this track";
        pendingDeleteId = $(this).data("id");
        $("#confirm-delete-filename").text(filename);
        deleteModal.show();
    });

    $("#confirm-delete-btn").on("click", function() {
        if (!pendingDeleteId) return;
        const id = pendingDeleteId;
        const confirmBtn = $(this);
        confirmBtn.prop("disabled", true).find(".spinner-border").show();

        $.ajax({
            url: `/audio/tracks/${id}`,
            method: "DELETE",
            success: function() {
                deleteModal.hide();
                confirmBtn.prop("disabled", false).find(".spinner-border").hide();
                pendingDeleteId = null;
                loadAudioTracks();
            },
            error: function(xhr) {
                confirmBtn.prop("disabled", false).find(".spinner-border").hide();
                deleteModal.hide();
                pendingDeleteId = null;
                pushErrMsg("Delete failed: " + (xhr.responseJSON?.error || "unknown error"));
            }
        });
    });

    document.getElementById("confirm-delete-track").addEventListener("hidden.bs.modal", function() {
        pendingDeleteId = null;
        $("#confirm-delete-btn").prop("disabled", false).find(".spinner-border").hide();
    });
});

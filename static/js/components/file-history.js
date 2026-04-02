function renderHistoryItem(op, index) {
    const statusClass = {
        completed: "success",
        failed:    "danger",
        canceled:  "secondary",
        started:   "warning"
    }[op.status] || "secondary";

    const date = op.started_at
        ? new Date(op.started_at).toLocaleString()
        : "—";

    let paramRows = "";
    if (op.params) {
        const labels = {
            codec: "Codec", resolution: "Resolution",
            crf: "CRF", acceleration: "Acceleration", preset: "Preset"
        };
        for (const [key, label] of Object.entries(labels)) {
            if (op.params[key] != null) {
                paramRows += `<tr><td class="text-muted">${label}</td><td>${op.params[key]}</td></tr>`;
            }
        }
    }

    let snapshotHtml = "";
    if (op.snapshot_before && op.snapshot_before.video && op.snapshot_before.video[0]) {
        const v = op.snapshot_before.video[0];
        snapshotHtml = `
            <div class="snapshot-before mt-2">
                <small class="text-muted d-block mb-1">Before:</small>
                <span class="badge bg-light text-dark border me-1">${v.codec || "—"}</span>
                <span class="badge bg-light text-dark border me-1">${v.resolution || "—"}</span>
                <span class="badge bg-light text-dark border">${v.bitrate || "—"}</span>
            </div>`;
    }

    let backupHtml = "";
    if (op.backup_path) {
        const deleted = op.backup_deleted === 1;
        const filename = op.backup_path.split("/").at(-1);
        const restoreBtn = (!deleted && index === 0)
            ? `<button class="btn btn-outline-secondary btn-sm restore-btn" data-operation-id="${op.id}">
                   <span class="spinner-border spinner-border-sm me-1" style="display:none"></span>
                   Restore original
               </button>`
            : "";
        const deleteBackupBtn = !deleted && index === 0
            ? `<button class="btn btn-outline-secondary btn-sm delete-backup-btn ms-1" data-operation-id="${op.id}" data-filename="${filename}" title="delete backup">
                   <span class="spinner-border spinner-border-sm" style="display:none"></span>
                   <i class="bi bi-trash"></i>
               </button>`
            : "";
        backupHtml = `
            <div class="mt-2 d-flex align-items-center gap-2">
                <small class="text-muted">Backup: </small>
                ${deleted
                    ? `<small class="text-danger"><i class="bi bi-trash"></i> Deleted</small>`
                    : `<small class="text-success"><i class="bi bi-hdd"></i> ${filename}</small>${restoreBtn}${deleteBackupBtn}`
                }
            </div>
            <div class="restore-progress mt-2" data-operation-id="${op.id}" style="display:none">
                <div class="progress" style="height: 6px">
                    <div class="progress-bar progress-bar-striped progress-bar-animated" style="width: 0%"></div>
                </div>
                <small class="text-muted restore-percent">0%</small>
            </div>`;
    }

    return `
        <li class="list-group-item history-item">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <span class="badge bg-${statusClass} me-2">${op.status}</span>
                    <span class="fw-semibold">${op.type}</span>
                </div>
                <small class="text-muted">${date}</small>
            </div>
            ${paramRows ? `<table class="table table-sm mb-0 mt-2 params-table"><tbody>${paramRows}</tbody></table>` : ""}
            ${snapshotHtml}
            ${backupHtml}
        </li>`;
}

function loadFileHistory(filePath) {
    const card = document.getElementById("file-history");
    const loading = card.querySelector(".history-loading");
    const empty = card.querySelector(".history-empty");
    const list = card.querySelector(".history-list");

    loading.style.display = "";
    empty.style.display = "none";
    list.style.display = "none";

    $.getJSON(`/file-history?path=${encodeURIComponent(filePath)}`, function(operations) {
        loading.style.display = "none";
        if (!operations.length) {
            empty.style.display = "";
            return;
        }
        list.innerHTML = operations.map(renderHistoryItem).join("");
        list.style.display = "";
    }).fail(function() {
        loading.textContent = "Failed to load history";
    });
}

$(document).ready(function() {
    if (typeof mediaInfo !== "undefined") {
        loadFileHistory(mediaInfo.path);
    }

    socket.on("completed", function(data) {
        if (typeof mediaInfo !== "undefined" && data.task.file === mediaInfo.path) {
            loadFileHistory(mediaInfo.path);
        }
    });

    socket.on("restore-progress", function(data) {
        const bar = $(`.restore-progress[data-operation-id="${data.operation_id}"]`);
        bar.show();
        bar.find(".progress-bar").css("width", data.percent + "%");
        bar.find(".restore-percent").text(data.percent + "%");
    });

    socket.on("restore-completed", function(data) {
        if (typeof mediaInfo !== "undefined" && data.file === mediaInfo.path) {
            window.location.reload();
        }
    });

    socket.on("restore-error", function(data) {
        const btn = $(`.restore-btn[data-operation-id="${data.operation_id}"]`);
        btn.prop("disabled", false).find(".spinner-border").hide();
        $(`.restore-progress[data-operation-id="${data.operation_id}"]`).hide();
        pushErrMsg(`Restore failed: ${data.message}`);
    });

    socket.on("restore-canceled", function(data) {
        const btn = $(`.restore-btn[data-operation-id="${data.operation_id}"]`);
        btn.prop("disabled", false).find(".spinner-border").hide();
        $(`.restore-progress[data-operation-id="${data.operation_id}"]`).hide();
    });

    let pendingDeleteBackupId = null;
    const deleteBackupModal = new bootstrap.Modal(document.getElementById("confirm-delete-backup"));

    $("#file-history").on("click", ".delete-backup-btn", function() {
        pendingDeleteBackupId = $(this).data("operation-id");
        $("#confirm-delete-backup-filename").text($(this).data("filename"));
        deleteBackupModal.show();
    });

    $("#confirm-delete-backup-btn").on("click", function() {
        if (!pendingDeleteBackupId) return;
        const id = pendingDeleteBackupId;
        const confirmBtn = $(this);
        confirmBtn.prop("disabled", true).find(".spinner-border").show();

        $.ajax({
            url: "/delete-backup",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({ operation_id: id }),
            success: function() {
                deleteBackupModal.hide();
                confirmBtn.prop("disabled", false).find(".spinner-border").hide();
                pendingDeleteBackupId = null;
                if (typeof mediaInfo !== "undefined") loadFileHistory(mediaInfo.path);
            },
            error: function(xhr) {
                confirmBtn.prop("disabled", false).find(".spinner-border").hide();
                deleteBackupModal.hide();
                pendingDeleteBackupId = null;
                pushErrMsg("Delete backup failed: " + (xhr.responseJSON?.error || "unknown error"));
            }
        });
    });

    document.getElementById("confirm-delete-backup").addEventListener("hidden.bs.modal", function() {
        pendingDeleteBackupId = null;
        $("#confirm-delete-backup-btn").prop("disabled", false).find(".spinner-border").hide();
    });

    $("#file-history").on("click", ".restore-btn", function() {
        const btn = $(this);
        const operationId = btn.data("operation-id");
        btn.prop("disabled", true).find(".spinner-border").show();

        $.ajax({
            url: "/restore-original",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({operation_id: operationId}),
            error: function(xhr) {
                btn.prop("disabled", false).find(".spinner-border").hide();
                const msg = xhr.responseJSON?.error || "Unknown error";
                pushErrMsg(`Restore failed: ${msg}`);
            }
        });
    });
});

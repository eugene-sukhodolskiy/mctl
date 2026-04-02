function loadOriginals() {
    $.getJSON("/originals/list", function(items) {
        const empty = $(".originals-empty");
        const table = $(".originals-table");
        const tbody = table.find("tbody");

        tbody.empty();
        if (!items.length) {
            empty.show(); table.hide();
            return;
        }

        empty.hide(); table.show();
        items.forEach(item => {
            const date = item.started_at
                ? new Date(item.started_at).toLocaleString()
                : "—";
            const sourceCell = item.source_name
                ? `<a href="/single?id=${item.source_id}">${item.source_name}</a>`
                : `<span class="text-muted">—</span>`;
            const restoreBtn = item.operation_id
                ? `<button class="btn btn-outline-secondary btn-sm btn-restore-original d-inline-flex align-items-center gap-1"
                           data-operation-id="${item.operation_id}"
                           data-backup-name="${item.backup_name}"
                           title="restore">
                       <span class="spinner-border spinner-border-sm" style="display:none"></span>
                       <i class="bi bi-arrow-counterclockwise"></i>
                   </button>`
                : '';
            tbody.append(`
                <tr data-backup-path="${item.backup_path}">
                    <td>${sourceCell}</td>
                    <td><small class="text-muted">${item.backup_name}</small></td>
                    <td><small class="text-muted">${formatBytes(item.size_bytes)}</small></td>
                    <td><small class="text-muted">${date}</small></td>
                    <td class="d-flex gap-1 justify-content-end">
                        ${restoreBtn}
                        <button class="btn btn-outline-secondary btn-sm btn-delete-original"
                                data-operation-id="${item.operation_id || ''}"
                                data-backup-path="${item.backup_path}"
                                data-backup-name="${item.backup_name}"
                                title="delete">
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
    loadOriginals();

    // — Restore —
    let pendingRestoreId = null;
    const restoreModal  = new bootstrap.Modal(document.getElementById("confirm-restore"));
    const progressModal = new bootstrap.Modal(document.getElementById("restore-progress-modal"));

    $(document).on("click", ".btn-restore-original", function() {
        pendingRestoreId = $(this).data("operation-id");
        $("#confirm-restore-filename").text($(this).data("backup-name"));
        restoreModal.show();
    });

    $("#confirm-restore-btn").on("click", function() {
        if (!pendingRestoreId) return;
        const id = pendingRestoreId;
        const confirmBtn = $(this);
        confirmBtn.prop("disabled", true).find(".spinner-border").show();

        $("#restore-progress-filename").text($(`[data-operation-id="${id}"]`).data("backup-name"));
        $("#restore-progress-bar").css("width", "0%");
        $("#restore-progress-pct").text("0%");

        $.ajax({
            url: "/restore-original",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({ operation_id: id }),
            success: function() {
                restoreModal.hide();
                confirmBtn.prop("disabled", false).find(".spinner-border").hide();
                pendingRestoreId = null;
                progressModal.show();
            },
            error: function(xhr) {
                confirmBtn.prop("disabled", false).find(".spinner-border").hide();
                restoreModal.hide();
                pendingRestoreId = null;
                pushErrMsg("Restore failed: " + (xhr.responseJSON?.error || "unknown error"));
            }
        });
    });

    document.getElementById("confirm-restore").addEventListener("hidden.bs.modal", function() {
        pendingRestoreId = null;
        $("#confirm-restore-btn").prop("disabled", false).find(".spinner-border").hide();
    });

    socket.on("restore-progress", function(data) {
        $("#restore-progress-bar").css("width", data.percent + "%");
        $("#restore-progress-pct").text(data.percent + "%");
    });

    socket.on("restore-completed", function() {
        progressModal.hide();
        loadOriginals();
    });

    socket.on("restore-error", function(data) {
        progressModal.hide();
        pushErrMsg("Restore failed: " + data.message);
    });

    socket.on("restore-canceled", function() {
        progressModal.hide();
    });

    // — Delete —
    let pendingDeleteBtn = null;
    const deleteModal = new bootstrap.Modal(document.getElementById("confirm-delete-original"));

    $(document).on("click", ".btn-delete-original", function() {
        pendingDeleteBtn = $(this);
        $("#confirm-delete-original-filename").text($(this).data("backup-name"));
        deleteModal.show();
    });

    $("#confirm-delete-original-btn").on("click", function() {
        if (!pendingDeleteBtn) return;
        const btn = pendingDeleteBtn;
        const confirmBtn = $(this);
        confirmBtn.prop("disabled", true).find(".spinner-border").show();

        const operationId = btn.data("operation-id") || null;
        const backupPath  = btn.data("backup-path");
        const payload = operationId
            ? { operation_id: operationId }
            : { backup_path: backupPath };

        $.ajax({
            url: "/delete-backup",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify(payload),
            success: function() {
                deleteModal.hide();
                confirmBtn.prop("disabled", false).find(".spinner-border").hide();
                pendingDeleteBtn = null;
                loadOriginals();
            },
            error: function(xhr) {
                confirmBtn.prop("disabled", false).find(".spinner-border").hide();
                deleteModal.hide();
                pendingDeleteBtn = null;
                pushErrMsg("Delete failed: " + (xhr.responseJSON?.error || "unknown error"));
            }
        });
    });

    document.getElementById("confirm-delete-original").addEventListener("hidden.bs.modal", function() {
        pendingDeleteBtn = null;
        $("#confirm-delete-original-btn").prop("disabled", false).find(".spinner-border").hide();
    });
});

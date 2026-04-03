// ─── Rename ───────────────────────────────────────────────────────────────────

function initRename() {
    const display    = $('#file-title-display');
    const editRow    = $('#file-title-edit');
    const input      = $('#file-title-input');
    const confirmBtn = $('#file-title-confirm');
    const cancelBtn  = $('#file-title-cancel');

    function enterEdit() {
        display.hide();
        editRow.css('display', 'flex');
        input.val(mediaInfo.name).focus().select();
    }

    function exitEdit() {
        editRow.hide();
        display.show();
    }

    function submitRename() {
        const newName = input.val().trim();
        if (!newName || newName === mediaInfo.name) { exitEdit(); return; }

        confirmBtn.prop('disabled', true).find('.spinner-border').show();
        confirmBtn.find('i').hide();

        $.ajax({
            url: '/rename-file',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ path: mediaInfo.path, name: newName }),
            success: function(resp) {
                mediaInfo.name = resp.new_name;
                mediaInfo.path = resp.new_path;
                display.find('.file-title').text(resp.new_name);
                $('#file-path-display').text('Path: ' + resp.new_path);
                exitEdit();
            },
            error: function(xhr) {
                pushErrMsg('Rename failed: ' + (xhr.responseJSON?.error || 'unknown error'));
                exitEdit();
            },
            complete: function() {
                confirmBtn.prop('disabled', false).find('.spinner-border').hide();
                confirmBtn.find('i').show();
            }
        });
    }

    display.on('click', enterEdit);
    confirmBtn.on('click', submitRename);
    cancelBtn.on('click', exitEdit);
    input.on('keydown', function(e) {
        if (e.key === 'Enter') submitRename();
        if (e.key === 'Escape') exitEdit();
    });
}

$(document).ready(function() {
    initRename();
    const deleteFileModal = new bootstrap.Modal(document.getElementById("confirm-delete-file"));

    let deleteFileLocked = false;
    $.getJSON("/file-status?path=" + encodeURIComponent(mediaInfo.path), function(data) {
        deleteFileLocked = data.transcoding;
    });
    socket.on("progress",      function(data) { if (data.task.file === mediaInfo.path) deleteFileLocked = true;  });
    socket.on("copy-progress", function(data) { if (data.file === mediaInfo.path)      deleteFileLocked = true;  });
    socket.on("completed",     function(data) { if (data.task.file === mediaInfo.path) deleteFileLocked = false; });
    socket.on("error",         function(data) { if (data.task.file === mediaInfo.path) deleteFileLocked = false; });
    socket.on("canceled",      function(data) { if (data.task.file === mediaInfo.path) deleteFileLocked = false; });

    $("#btn-delete-file").on("click", function() {
        if (deleteFileLocked) {
            pushInfoMsg("Cannot delete file while transcoding is in progress.");
            return;
        }
        deleteFileModal.show();
    });

    $("#confirm-delete-file-btn").on("click", function() {
        const btn = $(this);
        btn.prop("disabled", true).find(".spinner-border").show();

        $.ajax({
            url: "/delete-file",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({ path: mediaInfo.path }),
            success: function() {
                window.location.href = "/";
            },
            error: function(xhr) {
                btn.prop("disabled", false).find(".spinner-border").hide();
                deleteFileModal.hide();
                pushErrMsg("Delete failed: " + (xhr.responseJSON?.error || "unknown error"));
            }
        });
    });
});

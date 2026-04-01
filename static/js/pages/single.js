$(document).ready(function() {
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

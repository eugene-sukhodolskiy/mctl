function initThumbnails() {
    const row = document.querySelector(".thumbnails-row");
    if (!row) return;

    const fileId = row.dataset.fileId;
    if (!fileId || fileId === "None") {
        row.remove();
        return;
    }

    const lightbox = new bootstrap.Modal(document.getElementById("thumb-lightbox"));
    const lightboxImg = document.querySelector(".lightbox-img");

    $.getJSON(`/thumbnails/${fileId}`, function(urls) {
        row.innerHTML = "";
        if (!urls.length) {
            row.remove();
            return;
        }
        urls.forEach(url => {
            const img = document.createElement("img");
            img.src = url;
            img.className = "thumb-img";
            img.addEventListener("click", () => {
                lightboxImg.src = url;
                lightbox.show();
            });
            row.appendChild(img);
        });
    }).fail(function() {
        row.remove();
    });
}

$(document).ready(function() {
    initThumbnails();

    socket.on("completed", function(data) {
        if (typeof mediaInfo !== "undefined" && data.task.file === mediaInfo.path) {
            // thumbnails will refresh on page reload (triggered by single-transcoding.js)
        }
    });
});

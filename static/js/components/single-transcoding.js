function singleTranscodingInit() {
    const codecCRFMap = {
        "libx264": [0, 51],
        "libx265": [0, 51],
        "libvpx-vp9": [0, 63],
        "libaom-av1": [0, 63]
    };

    const maxResolution = $(`[name="resolution"]`).data("max-resolution");
    $(`[name="resolution"] option`).each(function(){
        parseInt($(this).attr("value")) > maxResolution 
            ? $(this).attr("disabled", "disabled") 
            : !$(`[name="resolution"] option[selected]`).length && $(this).attr("selected", "selected")
    });

    $(".show-transcodate-form").on("click", function(){
        const formContainer = $(".transcodate-form-container");
        if(formContainer.is(":visible")) {
            formContainer.slideUp();
        } else {
            formContainer.slideDown();
        }
    });

    $(".close-transcodate-form-container").on("click", function(){
        const formContainer = $(".transcodate-form-container");
        formContainer.slideUp();
    });

    const progressContainer = $("#progress");
    progressContainer.pushNewMessage = (msg) => {
        !progressContainer.is(":visible") && progressContainer.slideDown();
        progressContainer.html(msg);
    };
    // Listen for copy progress
    socket.on("copy-progress", (data) => {
        if(progressContainer.data("file-path") != data.file) return;

        $(".transcodate-form-container").slideUp();
        $(".show-transcodate-form").hide();
        $(".transcodate-form-container .run-transcodate").prop("disabled", false).find(".spinner-border").hide();
        $(".transcodate-form-container .run-transcodate").hide();

        const progressBar = $(".progress-bar-container");
        progressBar.find(".progress-phase-label").text("copying backup...");
        progressBar.find(".progress-phase-pct").text(data.percent + "%");
        progressBar.find(".progress-bar").removeClass("bg-success").addClass("bg-warning");
        progressBar.find(".progress-bar-line")[0].setProgressValue(data.percent);
        if(!progressBar.is(":visible")) progressBar.show();
    });

    // Listen for progress updates
    socket.on("progress", (data) => {
        if(progressContainer.data("file-path") != data.task.file) {
            return;
        }

        progressContainer.pushNewMessage(data.message);
        $(".transcodate-form-container").slideUp();
        $(".show-transcodate-form").hide();
        $(".stop-transcoding").show();
        $(".stop-transcoding").attr("data-task_id", data.task.id);
        $(".transcodate-form-container .run-transcodate").prop("disabled", false).find(".spinner-border").hide();
        $(".transcodate-form-container .run-transcodate").hide();

        const progressBar = $(".progress-bar-container");
        progressBar.find(".progress-phase-label").text("transcoding...");
        progressBar.find(".progress-phase-pct").text("");
        progressBar.find(".progress-bar").removeClass("bg-warning").addClass("bg-success");

        let time = getTimeFromTranscodingProgressMessage(data.message);
        const mInf = getMediaInfo(data.task.file);
        if(!mInf) return;

        const progressPercentage = calcTranscodingProgress(time, mInf.info.container.duration);
        progressBar.find(".progress-bar-line")[0].setProgressValue(progressPercentage);
        if(!progressBar.is(":visible")) progressBar.show();
    });

    function resetProgressBar() {
        const progressBar = $(".progress-bar-container");
        progressBar.find(".progress-bar-line")[0].setProgressValue(0);
        progressBar.find(".progress-bar").removeClass("bg-warning").addClass("bg-success");
        progressBar.find(".progress-phase-label").text("");
        progressBar.find(".progress-phase-pct").text("");
        progressBar.hide();
    }

    // Listen for completion
    socket.on("completed", (data) => {
        if(progressContainer.data("file-path") != data.task.file) return;

        progressContainer.pushNewMessage(
            `Completed! <button class="btn btn-sm btn-outline-secondary ms-2" onclick="window.location.reload()">
                <i class="bi bi-arrow-clockwise"></i> Refresh page
            </button>`
        );
        $(".show-transcodate-form").show();
        $(".stop-transcoding").prop("disabled", false).find(".spinner-border").hide();
        $(".stop-transcoding").hide();
        $(".transcodate-form-container .run-transcodate").show();
        resetProgressBar();
    });

    // Listen for errors
    socket.on("error", (data) => {
        if(progressContainer.data("file-path") != data.task.file) return;

        progressContainer.pushNewMessage(data.message);
        $(".show-transcodate-form").show();
        $(".stop-transcoding").prop("disabled", false).find(".spinner-border").hide();
        $(".stop-transcoding").hide();
        $(".transcodate-form-container .run-transcodate").show();
        resetProgressBar();
    });

    socket.on("canceled", (data) => {
        if(progressContainer.data("file-path") != data.task.file) return;

        progressContainer.pushNewMessage(data.message);
        $(".stop-transcoding").prop("disabled", false).find(".spinner-border").hide();
        $(".stop-transcoding").hide();
        $(".show-transcodate-form").show();
        $(".transcodate-form-container .run-transcodate").show();
        resetProgressBar();
    });

    async function submitTranscoding() {
        const formContiner = $(".transcodate-form-container");
        const fields = formContiner.find("[name]");
        const runBtn = $(".transcodate-form-container .run-transcodate");
        runBtn.prop("disabled", true).find(".spinner-border").show();

        const data = {};
        for(let field of fields) {
            field = $(field);
            if(field.attr("type") === "checkbox") {
                data[field.attr("name")] = field.is(":checked");
            } else {
                data[field.attr("name")] = field.val();
            }
        }

        data["crf"] = "" + Math.abs(data["crf"]);

        const response = await fetch("/process-media", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            document.getElementById("progress").innerText = "Processing started...";
        } else {
            const error = await response.json();
            runBtn.prop("disabled", false).find(".spinner-border").hide();
            pushErrMsg(error.error);
        }
    }

    const deleteOriginalModal = new bootstrap.Modal(document.getElementById("confirm-delete-original"));

    $(".transcodate-form-container .run-transcodate").on("click", function() {
        if ($("[name='delete_original']").is(":checked")) {
            deleteOriginalModal.show();
        } else {
            submitTranscoding();
        }
    });

    $("#confirm-run-transcode-btn").on("click", function() {
        deleteOriginalModal.hide();
        submitTranscoding();
    });

    $("#codec").on("change", function(){
        const crf = $(`[name="crf"]`);

        const codec = $(this).val();
        crf.attr("min", codecCRFMap[codec][0]);
        crf.attr("max", codecCRFMap[codec][1]);
        if(parseInt(crf.val()) > codecCRFMap[codec][1]) {
            crf.val(codecCRFMap[codec][1]);
        }

        crf.parent().find(".crf-range").text(`${codecCRFMap[codec][0]}-${codecCRFMap[codec][1]}`);

        // toggle form of preset
        const presetLibxForm = $(`[name="preset-libx"]`);
        const presetVP9Form = $(`[name="preset-vp9"]`);
        const presetAV1Form = $(`[name="preset-av1"]`);
        if(codec == "libx264" || codec == "libx265") {
            presetLibxForm.show();
            presetVP9Form.hide();
            presetAV1Form.hide();
        } else if(codec == "libaom-av1"){
            presetLibxForm.hide();
            presetVP9Form.hide();
            presetAV1Form.show();
        } else if(codec == "libvpx-vp9") {
            presetLibxForm.hide();
            presetVP9Form.show();
            presetAV1Form.hide();
        }
    });

    $(`[name="crf"]`).on("input", function(){
        const val = parseInt($(this).val());

        if(isNaN(val)) {
            $(this).val(0);
            return;
        }

        if(val < 0) {
            $(this).val(0);
            return;
        }

        const max = parseInt($(this).attr("max"));
        if(val > max) {
            $(this).val(max);
        }
    });

    $(".stop-transcoding").on("click", function(){
        $(this).prop("disabled", true).find(".spinner-border").show();
        stopTranscoding($(this).data("task_id"));
    });
}

function stopTranscoding(taskId) {
    if(taskId && taskId != "undefined") {
        $(".stop-transcoding").prop("disabled", false).find(".spinner-border").hide();
        $(".stop-transcoding").hide();

        $.getJSON(`/stop-transcoding?task_id=${taskId}`, function(resp) {
            if(resp.status == "stopped" && resp.task_id == taskId) {
                processContainer.slideUp();
                setTimeout(() => processContainer.html(""), 200);
            }
        });
    }
} 

$(document).ready(function() {
    singleTranscodingInit();
});
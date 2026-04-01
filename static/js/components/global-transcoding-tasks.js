const globalTasks = {};
const copyTasks = {};   // keyed by file path during copy phase
const mediaInfoCenter = {};

// Title management
const taskPercents = {}; // 'copy:<path>' | 'tx:<taskId>' -> {percent, phase, file}
const pageBaseTitle = (typeof mediaInfo !== "undefined" && mediaInfo.name)
    ? mediaInfo.name
    : "mctl";

// Scan animation
let _scanAnimFrame = null;
let _scanAnimInterval = null;
const _scanFrames = ["*", "^", "#", "!", "$", "&", "?"];

function startScanTitleAnimation() {
    if (_scanAnimInterval) return;
    let i = 0;
    _scanAnimInterval = setInterval(() => {
        document.title = `${_scanFrames[i % _scanFrames.length]} scanning... ${pageBaseTitle}`;
        i++;
    }, 150);
}

function stopScanTitleAnimation() {
    if (_scanAnimInterval) {
        clearInterval(_scanAnimInterval);
        _scanAnimInterval = null;
    }
    updatePageTitle();
}

function updatePageTitle() {
    if (_scanAnimInterval) return; // scan animation takes priority
    const entries = Object.values(taskPercents);
    if (!entries.length) {
        document.title = pageBaseTitle;
        return;
    }

    const isFilePage = typeof mediaInfo !== "undefined";
    if (isFilePage) {
        const thisFile = entries.find(e => e.file === mediaInfo.path);
        if (thisFile) {
            document.title = `[${thisFile.percent}% ${thisFile.phase}] ${pageBaseTitle}`;
            return;
        }
    }

    const avg = Math.round(entries.reduce((s, e) => s + e.percent, 0) / entries.length);
    document.title = `[avg ${avg}%] ${pageBaseTitle}`;
}

function createCopyTaskView(filePath) {
	const filename = filePath.split("/").at(-1);
	const href = `/single?path=${encodeURIComponent(filePath)}`;
	const li = document.createElement('li');
	li.classList.add("list-group-item", "task");
	li.dataset.copyFile = filePath;
	li.innerHTML = `
		<div class="file">
			<div class="circle-progress-bar" data-value="0" data-bar-color="#e0af68" data-bar-stroke="4" data-bar-size="30"></div>
			<div>
				<a href="${href}" class="link-primary">${filename}</a>
				<div class="copy-phase-label" style="font-size:0.75rem; color: var(--tn-muted)">copying backup...</div>
			</div>
			<span class="progress-percent" style="opacity:.7">0%</span>
		</div>
		<div class="control">
			<button class="btn btn-outline-secondary btn-sm" disabled title="copying in progress">
				<i class="bi bi-stop-fill"></i>
			</button>
		</div>
	`;
	initSingleCircleProgressBar(li.querySelector(".circle-progress-bar"));
	return li;
}

function createEmptyTaskView(taskId) {
	const li = document.createElement('li');
	li.classList.add("list-group-item");
	li.classList.add("task");
	li.dataset.taskId = taskId;

	let html = `
		<div class="file">
      <div class="circle-progress-bar" data-value="0" data-bar-color="#198754" data-bar-stroke="4" data-bar-size="30"></div>
      <a href="" class="link-primary"></a>
      <span class="progress-percent" style="opacity: .7">0%</span>
    </div>
    <div class="control">
      <button class="btn btn-danger cancel" data-task-id="${ taskId }"><i class="bi bi-stop-fill"></i> Stop</button>
      <div class="spinner-border text-secondary" role="status" style="display: none">
			  <span class="visually-hidden">Loading...</span>
			</div>
    </div>
	`;

	li.innerHTML = html;
	initSingleCircleProgressBar(li.querySelector(".circle-progress-bar"));
	return initTaskView(li);
}

function getTotalActiveTasks() {
	return Object.keys(globalTasks).length + Object.keys(copyTasks).length;
}

function updateTasksUI() {
	const total = getTotalActiveTasks();
	$(".total-tasks").text(total > 0 ? total : "");
	if (total > 0) {
		$(".empty-tasks-message").hide();
	} else {
		$(".empty-tasks-message").show();
	}
}

function initTaskView(view) {
	view.querySelector(".control .cancel").addEventListener("click", e => {
		const taskId = e.currentTarget.dataset.taskId;
		$(e.currentTarget).hide();
		$(e.currentTarget).parent().find(".spinner-border").show();

		$.getJSON(`/stop-transcoding?task_id=${taskId}`, function(resp) {
      if(resp.status == "stopped" && resp.task_id == taskId) {
      	if(typeof globalTasks[resp.task_id] != "undefined") {
      		// delete globalTasks[resp.task_id];
      	}
      } else {
      	pushErrMsg("Failed to complete request to stop transcoding");
      }
    });
	});

	return view;
}

function updateExistsView(data, view) {
	const taskContainer = $(view);
	const href = `/single?path=${encodeURIComponent(data.task.file)}`;
	const fileLink = taskContainer.find(".file a");

	if(fileLink.attr("href") != href) {
		fileLink.text(data.task.file.split("/").at(-1));
		fileLink.attr("href", href);
	}

	let time = getTimeFromTranscodingProgressMessage(data.message);
	const mInf = getMediaInfo(data.task.file);

	if(!mInf) {
		return; // media info not yet loaded — keep showing 0%
	}

	const progressPercent = calcTranscodingProgress(time, mInf.info.container.duration);
	const displayPercent = (isNaN(progressPercent) || progressPercent < 0) ? 0 : Math.min(progressPercent, 99);

	const cpbar = taskContainer.find(".file .circle-progress-bar")[0];
	if(cpbar.dataset.value != displayPercent) {
		taskContainer.find(".file .progress-percent").text(`${displayPercent}%`);
		cpbar.dataset.value = displayPercent;
	}
}

function globalTranscodingTasksInit() {
	const tasksContainer = $(".transcoding-tasks-container > ul");

	socket.on("copy-progress", data => {
		if (typeof copyTasks[data.file] === "undefined") {
			const view = createCopyTaskView(data.file);
			tasksContainer.append(view);
			copyTasks[data.file] = { view };
			updateTasksUI();
		}

		const view = copyTasks[data.file].view;
		const cpbar = view.querySelector(".circle-progress-bar");
		cpbar.dataset.value = data.percent;
		view.querySelector(".progress-percent").textContent = data.percent + "%";

		taskPercents[`copy:${data.file}`] = { percent: data.percent, phase: 'copying', file: data.file };
		updatePageTitle();
	});

	socket.on("progress", data => {
		if(typeof data.task.id == "undefined") {
			return;
		}

		// Remove copy-phase card if it exists for this file
		if (typeof copyTasks[data.task.file] !== "undefined") {
			$(copyTasks[data.task.file].view).remove();
			delete copyTasks[data.task.file];
			delete taskPercents[`copy:${data.task.file}`];
		}

		if(typeof globalTasks[data.task.id] == "undefined") {
			const view = createEmptyTaskView(data.task.id);
			tasksContainer.append(view);
			globalTasks[data.task.id] = { "data": data, "view": view };
		}

		updateExistsView(data, globalTasks[data.task.id].view);
		updateTasksUI();

		const displayPercent = (function() {
			const cpbar = globalTasks[data.task.id]?.view?.querySelector(".circle-progress-bar");
			return cpbar ? parseInt(cpbar.dataset.value) || 0 : 0;
		})();
		taskPercents[`tx:${data.task.id}`] = { percent: displayPercent, phase: 'transcoding', file: data.task.file };
		updatePageTitle();
	});

	function cleanupTask(data) {
		if (typeof copyTasks[data.task.file] !== "undefined") {
			$(copyTasks[data.task.file].view).remove();
			delete copyTasks[data.task.file];
			delete taskPercents[`copy:${data.task.file}`];
		}
		if (typeof globalTasks[data.task.id] !== "undefined") {
			$(globalTasks[data.task.id].view).remove();
			delete globalTasks[data.task.id];
			delete taskPercents[`tx:${data.task.id}`];
		}
		updateTasksUI();
		updatePageTitle();
	}

	socket.on("completed", data => { cleanupTask(data); });
	socket.on("canceled",  data => { cleanupTask(data); });

	socket.on("error", data => {
		cleanupTask(data);
	});

	socket.on("medialib-scaning-process", () => startScanTitleAnimation());
	socket.on("medialib-scaning-complete", () => stopScanTitleAnimation());
}

function getMediaInfo(path) {
	if(typeof mediaInfoCenter[path] == "undefined") {
		getSingleMediaFileInfo(path, resp => {
			console.log(resp);
			mediaInfoCenter[resp.path] = resp;
		});

		return false;
	}

	return mediaInfoCenter[path];
}

$(document).ready(function() {
	if(typeof mediaInfo != "undefined") {
		mediaInfoCenter[mediaInfo.path] = mediaInfo;
	}

	document.title = pageBaseTitle;
	globalTranscodingTasksInit();

	$.getJSON("/scan-status", function(data) {
		if (data.scanning) startScanTitleAnimation();
	});
});
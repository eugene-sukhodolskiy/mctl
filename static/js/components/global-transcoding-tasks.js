const globalTasks = {};
const copyTasks = {};   // keyed by file path during copy phase
const genericTasks = {}; // keyed by operation key (audio-*, restore:*)
const mediaInfoCenter = {};

// Title management
const taskPercents = {}; // key -> {percent, phase, file}
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

// ─── Generic progress card ────────────────────────────────────────────────────

function createProgressTaskView(key, filePath, fileId, label, barColor, stopUrl) {
	const filename = filePath.split("/").at(-1);
	const href = fileId ? `/single?id=${fileId}` : `/single?path=${encodeURIComponent(filePath)}`;
	const li = document.createElement('li');
	li.classList.add("list-group-item", "task");
	li.dataset.taskKey = key;

	const stopBtn = stopUrl
		? `<button class="btn btn-danger btn-sm process-stop" data-stop-url="${stopUrl}">
				<i class="bi bi-stop-fill"></i> Stop
				<span class="spinner-border spinner-border-sm" style="display:none"></span>
			</button>`
		: `<button class="btn btn-outline-secondary btn-sm" disabled title="cannot cancel">
				<i class="bi bi-stop-fill"></i>
			</button>`;

	li.innerHTML = `
		<div class="file">
			<div class="circle-progress-bar" data-value="0" data-bar-color="${barColor}" data-bar-stroke="4" data-bar-size="30"></div>
			<div>
				<a href="${href}" class="link-primary">${filename}</a>
				<div class="task-phase-label" style="font-size:0.75rem; color: var(--tn-muted)">${label}</div>
			</div>
			<span class="progress-percent" style="opacity:.7">0%</span>
		</div>
		<div class="control">${stopBtn}</div>
	`;
	initSingleCircleProgressBar(li.querySelector(".circle-progress-bar"));

	const stopBtnEl = li.querySelector(".process-stop");
	if (stopBtnEl) {
		stopBtnEl.addEventListener("click", function() {
			const url = this.dataset.stopUrl;
			this.disabled = true;
			this.querySelector(".spinner-border").style.display = "inline-block";
			this.querySelector("i").style.display = "none";
			$.getJSON(url, function(resp) {
				if (resp.status !== "stopped") {
					pushErrMsg("Failed to stop process");
				}
			}).fail(function() {
				pushErrMsg("Failed to stop process");
			});
		});
	}

	return li;
}

function updateProgressTaskView(view, percent) {
	const cpbar = view.querySelector(".circle-progress-bar");
	if (cpbar && cpbar.dataset.value != percent) {
		cpbar.dataset.value = percent;
		view.querySelector(".progress-percent").textContent = percent + "%";
	}
}

// ─── Copy task (copy phase of transcoding, not cancellable) ───────────────────

function createCopyTaskView(filePath, fileId) {
	return createProgressTaskView(
		`copy:${filePath}`,
		filePath,
		fileId,
		"copying backup...",
		"#e0af68",
		null  // no stop button during copy phase
	);
}

// ─── Transcoding task (cancellable) ───────────────────────────────────────────

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
	return Object.keys(globalTasks).length
		+ Object.keys(copyTasks).length
		+ Object.keys(genericTasks).length;
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
	const href = data.task.file_id
		? `/single?id=${data.task.file_id}`
		: `/single?path=${encodeURIComponent(data.task.file)}`;
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

// ─── Generic task helpers ─────────────────────────────────────────────────────

const TASK_COLORS = {
	'audio-extract': '#7aa2f7',
	'audio-remove':  '#f7768e',
	'audio-add':     '#9ece6a',
	'restore':       '#bb9af7',
};

const TASK_LABELS = {
	'audio-extract': 'extracting audio...',
	'audio-remove':  'removing audio track...',
	'audio-add':     'adding audio track...',
	'restore':       'restoring original...',
};

function buildStopUrl(key, opType) {
	if (opType === 'restore') {
		const operationId = key.split(':')[1];
		return `/restore-stop?operation_id=${operationId}`;
	}
	// audio-extract, audio-remove, audio-add
	return `/audio/stop?key=${encodeURIComponent(key)}`;
}

function ensureGenericTask(tasksContainer, key, opType, filePath, fileId) {
	if (typeof genericTasks[key] === "undefined") {
		const color = TASK_COLORS[opType] || '#aaaaaa';
		const label = TASK_LABELS[opType] || opType;
		const stopUrl = buildStopUrl(key, opType);
		const view = createProgressTaskView(key, filePath, fileId, label, color, stopUrl);
		tasksContainer.append(view);
		genericTasks[key] = { view, file: filePath };
		updateTasksUI();
	}
}

function removeGenericTask(key, titleKey) {
	if (typeof genericTasks[key] !== "undefined") {
		$(genericTasks[key].view).remove();
		delete genericTasks[key];
	}
	if (titleKey) delete taskPercents[titleKey];
	updateTasksUI();
	updatePageTitle();
}

function globalTranscodingTasksInit() {
	const tasksContainer = $(".transcoding-tasks-container > ul");

	// ── Copy phase (transcoding backup) ─────────────────────────────────────
	socket.on("copy-progress", data => {
		const key = `copy:${data.file}`;
		if (typeof copyTasks[data.file] === "undefined") {
			const view = createCopyTaskView(data.file, data.file_id);
			view.dataset.taskKey = key;
			tasksContainer.append(view);
			copyTasks[data.file] = { view };
			updateTasksUI();
		}

		const view = copyTasks[data.file].view;
		updateProgressTaskView(view, data.percent);

		taskPercents[key] = { percent: data.percent, phase: 'copying', file: data.file };
		updatePageTitle();
	});

	// ── Transcoding (ffmpeg) phase ───────────────────────────────────────────
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

	function cleanupTranscodingTask(data) {
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

	socket.on("completed", data => { cleanupTranscodingTask(data); });
	socket.on("canceled",  data => { cleanupTranscodingTask(data); });
	socket.on("error",     data => { cleanupTranscodingTask(data); });

	// ── Audio extract ────────────────────────────────────────────────────────
	socket.on("audio-extract-progress", data => {
		const key = `audio-extract:${data.file}:${data.track_index}`;
		ensureGenericTask(tasksContainer, key, 'audio-extract', data.file, data.file_id);
		updateProgressTaskView(genericTasks[key].view, data.percent);
		taskPercents[key] = { percent: data.percent, phase: 'extracting', file: data.file };
		updatePageTitle();
	});
	socket.on("audio-extract-completed", data => {
		const key = `audio-extract:${data.file}:${data.track_index}`;
		removeGenericTask(key, key);
	});
	socket.on("audio-extract-error", data => {
		const key = `audio-extract:${data.file}:${data.track_index}`;
		removeGenericTask(key, key);
	});
	socket.on("audio-extract-canceled", data => {
		const key = `audio-extract:${data.file}:${data.track_index}`;
		removeGenericTask(key, key);
	});

	// ── Audio remove ─────────────────────────────────────────────────────────
	socket.on("audio-remove-progress", data => {
		const key = `audio-remove:${data.file}:${data.track_index}`;
		ensureGenericTask(tasksContainer, key, 'audio-remove', data.file, data.file_id);
		updateProgressTaskView(genericTasks[key].view, data.percent);
		taskPercents[key] = { percent: data.percent, phase: 'removing', file: data.file };
		updatePageTitle();
	});
	socket.on("audio-remove-completed", data => {
		const key = `audio-remove:${data.file}:${data.track_index}`;
		removeGenericTask(key, key);
	});
	socket.on("audio-remove-error", data => {
		const key = `audio-remove:${data.file}:${data.track_index}`;
		removeGenericTask(key, key);
	});
	socket.on("audio-remove-canceled", data => {
		const key = `audio-remove:${data.file}:${data.track_index}`;
		removeGenericTask(key, key);
	});

	// ── Audio add ────────────────────────────────────────────────────────────
	socket.on("audio-add-progress", data => {
		const key = `audio-add:${data.file}`;
		ensureGenericTask(tasksContainer, key, 'audio-add', data.file, data.file_id);
		updateProgressTaskView(genericTasks[key].view, data.percent);
		taskPercents[key] = { percent: data.percent, phase: 'adding audio', file: data.file };
		updatePageTitle();
	});
	socket.on("audio-add-completed", data => {
		const key = `audio-add:${data.file}`;
		removeGenericTask(key, key);
	});
	socket.on("audio-add-error", data => {
		const key = `audio-add:${data.file}`;
		removeGenericTask(key, key);
	});
	socket.on("audio-add-canceled", data => {
		const key = `audio-add:${data.file}`;
		removeGenericTask(key, key);
	});

	// ── Restore ──────────────────────────────────────────────────────────────
	socket.on("restore-progress", data => {
		const key = `restore:${data.operation_id}`;
		ensureGenericTask(tasksContainer, key, 'restore', data.file, data.file_id);
		updateProgressTaskView(genericTasks[key].view, data.percent);
		taskPercents[key] = { percent: data.percent, phase: 'restoring', file: data.file };
		updatePageTitle();
	});
	socket.on("restore-completed", data => {
		const key = `restore:${data.operation_id}`;
		removeGenericTask(key, key);
	});
	socket.on("restore-error", data => {
		const key = `restore:${data.operation_id}`;
		removeGenericTask(key, key);
	});
	socket.on("restore-canceled", data => {
		const key = `restore:${data.operation_id}`;
		removeGenericTask(key, key);
	});

	// ── Scan animation ───────────────────────────────────────────────────────
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

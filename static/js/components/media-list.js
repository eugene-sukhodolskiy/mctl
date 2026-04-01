function LSpinnerShow() {
	$(".loading-spinner-container").removeClass("d-none");
}

function LSpinnerHide() {
	$(".loading-spinner-container").addClass("d-none");
}

// Function to load media data
function loadMediaList() {
	LSpinnerShow();
	$("#media-table").addClass("d-none");
	$("#media-table_wrapper").addClass("d-none");

	const tableBody = $("#media-table tbody");
	tableBody.empty();

	$.ajax({
		url: "/media-list",
		method: "GET",
		success: function(resp) {
			if(resp.status == "scaning" && !resp.data.length) {
				return;
			}

			let data = resp.data;

			renderMediaList(data);
		},
		error: function(xhr, status, error) {
			LSpinnerHide();
			pushErrMsg("Error loading media list");
			console.error("Error loading media list:", error);
		}
	});
}

function rescanMediaLibHandler() {
	$("#do-rescan-media-lib").on("click", function(){
		if($(this).hasClass("disabled")) {
			return;
		}

		console.log('test');
		$.getJSON("/media-list/clear-cache").done(function(resp){
			if(resp.status) {
				document.getElementById("do-rescan-media-lib").setStateInprogress();
				return;
			}

			console.error("Error of rescan media library");
			pushErrMsg("Error of rescan media library");
		});
	});
}

function renderMediaList(data) {
	const tableBody = $("#media-table tbody");

	if(typeof data != "object") {
		return;
	}

	if (data.length > 0) {
		data.forEach((file, index) => {
			const videoRows = (file.info.video || [])
				.filter(v => v.codec !== 'mjpeg')
				.map(v => {
					const bitrate = v.bitrate && v.bitrate !== 'Unknown'
						? `<span class="stream-bitrate">${v.bitrate}</span>` : '';
					return `<div class="stream-row">
						<span class="badge bg-light border">${v.resolution || '—'}</span>
						<span class="badge bg-light border">${v.codec || '—'}</span>
						${bitrate}
					</div>`;
				}).join('');

			const audioRows = (file.info.audio || []).map(a => {
				const lang = (a.language || 'und').toLowerCase();
				const channels = a.layout || a.channels || '—';
				const bitrate = a.bitrate && a.bitrate !== 'Unknown'
					? `<span class="stream-bitrate">${a.bitrate}</span>` : '';
				const title = a.title
					? `<span class="stream-title">${a.title}</span>` : '';
				return `<div class="stream-row">
					<span class="badge lang-badge lang-${lang}">${lang}</span>
					<span class="badge bg-light border">${a.codec || '—'}</span>
					<span class="badge bg-light border">${channels}</span>
					${bitrate}
					${title}
				</div>`;
			}).join('');

			const details = `
				<div class="streams-section">
					<span class="stream-label">video</span>
					<div class="stream-rows">${videoRows || '<span class="text-muted small">—</span>'}</div>
				</div>
				<div class="streams-section">
					<span class="stream-label">audio</span>
					<div class="stream-rows">${audioRows || '<span class="text-muted small">—</span>'}</div>
				</div>
			`;

			const pathEncoded = encodeURIComponent(file.path);
			const transcodedBadge = file.transcoded
				? `<span class="badge-transcoded" title="transcoded"><i class="bi bi-check-circle-fill"></i> transcoded</span>`
				: '';

			tableBody.append(`
				<tr>
					<td>${index + 1}</td>
					<td>
						<div class="filename"><a href="/single?id=${file.id}">${file.name}</a>${transcodedBadge}</div>
						<div class="filepath">${file.path}</div>
						<div class="filedetails">${details}</div>
					</td>
					<td class="size_unit_${file.size_unit}" data-order="${file.size_bytes}">${file.size}${file.size_unit}</td>
				</tr>
			`);
		});
	} else {
		tableBody.append(`<tr><td colspan="3" class="text-center">No files found</td></tr>`);
	}

	if(!$('#media-table_wrapper').length && $('#media-table tbody td').length > 1) {            
		initMediaListTable();
	}

	LSpinnerHide();
	$("#media-table_wrapper").removeClass("d-none");
	$("#media-table").removeClass("d-none");
}

function initMediaListTable() {
	$('#media-table').DataTable({
		columnDefs: [
			{
				targets: "_all",
				render: function(data, type, row, meta) {
					var cell = meta.settings.aoData[meta.row].anCells[meta.col];
					if (type === 'sort' && cell) {
						var orderValue = $(cell).attr('data-order');
						return orderValue !== undefined ? orderValue : data;
					}
					return data;
				}
			}
		]
	});
}

let lastMediaLibScaningProcessMsg = "";

function initScaningProcessingView() {
	const activateBtn = document.getElementById("do-rescan-media-lib");
	activateBtn.setStateInprogress = () => {
		changeBtnStateToInProgress(activateBtn);
	}

	activateBtn.setStateDefault = () => {
		changeBtnStateToDefault(activateBtn);
	}


	const scaningProcessingContainer = $(".scaning-process-container");

	socket.on("medialib-scaning-process", data => {
		if(!scaningProcessingContainer.is(":visible")) {
			scaningProcessingContainer.html("");
			scaningProcessingContainer.slideDown();
			activateBtn.setStateInprogress();
		}

		if(lastMediaLibScaningProcessMsg == data.message) {
			return;
		}

		lastMediaLibScaningProcessMsg = data.message;
		scaningProcessingContainer.html(data.message);
	});
}

$(document).ready(function() {
	loadMediaList();
	rescanMediaLibHandler();
	initScaningProcessingView();

	socket.on("medialib-scaning-complete", resp => {
		if($('#media-table_wrapper').length) {
			$('#media-table').DataTable().destroy();
		}
		$("#media-table tbody").empty();

		renderMediaList(resp.data);

		$(".scaning-process-container").slideUp();
		document.getElementById("do-rescan-media-lib").setStateDefault();
	});
});
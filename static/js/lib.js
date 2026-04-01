function getSingleMediaFileInfo(filepath, callback) {
	$.getJSON(`/single-json?path=${ filepath }`, function(resp) {
		callback(resp);
	});
}

function getTimeFromTranscodingProgressMessage(message) {
	let time = "00:00:00";
	if(message.indexOf("time=") != -1 && message.indexOf("time=N/A") == -1) {
		time = message.split("time=")[1].split(" ")[0];
	}

	return time;
}

function calcTranscodingProgress(time, duration) {
	return Math.floor(timeToSeconds(time) / parseInt(duration) * 100);
}

function changeBtnStateToInProgress(btn) {
	if(btn.stateIsInprogress) {
		return;
	}

	btn.stateIsInprogress = true;
	$(btn).addClass("inprogress");
	$(btn).addClass("disabled");
}

function changeBtnStateToDefault(btn) {
	if(!btn.stateIsInprogress) {
		return;
	}

	btn.stateIsInprogress = false;
	$(btn).removeClass("inprogress");
	$(btn).removeClass("disabled");
}
function makeErrMsgViewHTML(msg) {
	return `
		<div class="error-item shadow alert alert-danger alert-dismissible fade" role="alert">
		  <strong>Error:</strong> ${ msg }
		  <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
		</div>
	`;
}

function initErrMsgView(view, drawTimeout, hideTimeout) {
	const tempContainer = document.createElement('div');
	tempContainer.innerHTML = view;

	view = tempContainer.querySelector(".error-item");
	
	setTimeout(() => view.classList.add("show"), drawTimeout);
	
	if(typeof hideTimeout != "undefined") {
		setTimeout(
			() => {
				view.classList.remove("show");
				setTimeout(() => $(view).remove(), 250);
			},
			hideTimeout + drawTimeout
		);
	}

	view.querySelector(".btn-close").addEventListener("click", e => {
		view.classList.remove("show");
	});

	return view;
}

function createErrMsg(msg) {
	let view = makeErrMsgViewHTML(msg);
	view = initErrMsgView(view, 100);

	return view;
}

function pushErrMsg(msg) {
	const container = $(".component.errors-center");
	const msgView = createErrMsg(msg);
	container.append(msgView);
}

function pushInfoMsg(msg) {
	const container = $(".component.errors-center");
	const html = `
		<div class="error-item shadow alert alert-info alert-dismissible fade" role="alert">
		  <i class="bi bi-info-circle me-1"></i>${msg}
		  <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
		</div>`;
	const view = initErrMsgView(html, 100, 4000);
	container.append(view);
}

$(document).ready(function() {

});
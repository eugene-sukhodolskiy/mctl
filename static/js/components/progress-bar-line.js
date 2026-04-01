$(document).ready(function(){
	$(".progress-bar-line").each(function() {
		this.setProgressValue = val => {
			if($(this).attr("aria-valuenow") == val) {
				return;
			}
			
			$(this).attr("aria-valuenow", val);
			const bar = $(this).find(".progress-bar");
			bar.css("width", `${ val }%`);
			bar.text(`${ val }%`);
		}
	});
});
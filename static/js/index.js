function makeProgressBar(props) {
	let html = `<svg viewBox="0 0 ${props.size} ${props.size}" class="progress-circle" width="${props.size}" height="${props.size}">
    <!-- Фон круга -->
    <circle
      class="circle-bg"
      cx="${props.size/2}"
      cy="${props.size/2}"
      r="${props.size/3}"
      fill="none"
      stroke="${props.trackColor}"
      stroke-width="${props.strokeWidth}"
    />
    <!-- Прогресс -->
    <circle
      class="circle-progress"
      cx="${props.size/2}"
      cy="${props.size/2}"
      r="${props.size/3}"
      fill="none"
      stroke="${props.fillColor}"
      stroke-width="${props.strokeWidth}"
      stroke-dasharray="100, 100"
      stroke-linecap="round"
    />
  </svg>`;

  return html;
}

function initSingleCircleProgressBar(view) {
  if(view.alreadyInitProgressBars) {
    return ;
  }

  $(view).html(makeProgressBar({
    "trackColor": view.dataset.barColor + "33",
    "fillColor": view.dataset.barColor,
    "strokeWidth": view.dataset.barStroke,
    "size": view.dataset.barSize
  }));

  setProgressBarVal(view, view.dataset.value);

  const targetElement = view;

  const observer = new MutationObserver((mutationsList) => {
    for (const mutation of mutationsList) {
      if (mutation.type === "attributes" && mutation.attributeName.startsWith("data-")) {
        const changedAttr = mutation.attributeName;
        const newValue = targetElement.getAttribute(changedAttr);

        setProgressBarVal(targetElement, newValue);
      }
    }
  });

  observer.observe(targetElement, {
    attributes: true,
    attributeFilter: ["data-value"],
  });

  view.alreadyInitProgressBars = true;
}

function initCircleProgressBars() {
  $(".circle-progress-bar[data-value]").each(function(){
    initSingleCircleProgressBar(view);
  });
}

function setProgressBarVal(target, percent) {
  const circle = target.querySelector(".circle-progress");
  const radius = circle.r.baseVal.value;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  circle.style.strokeDasharray = `${circumference - offset} ${circumference}`;
}

$(document).ready(function() {
	$(".duration-to-minutes[data-duration-in-seconds]").each(function() {
		const durationInSec = parseInt($(this).data("duration-in-seconds"));
		const durationInMinutes = Math.floor(durationInSec / 60);
		const leftSeconds = Math.floor(durationInSec - durationInMinutes * 60);
		$(this).text(`${durationInMinutes}m ${leftSeconds}s`);
	});

  initCircleProgressBars();
});
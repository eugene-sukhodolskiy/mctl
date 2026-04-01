const gulp = require("gulp");
const sass = require("gulp-sass")(require("sass"));
const sourcemaps = require("gulp-sourcemaps");
const watch = require("gulp-watch");
const cleanCSS = require("gulp-clean-css");
const concat = require("gulp-concat");
const uglify = require("gulp-uglify");

gulp.task("sass-build", () => {
	return gulp.src("./scss/index.scss")
		.pipe(sourcemaps.init())
		.pipe(sass().on("error", sass.logError))
		.pipe(concat("main.css"))
		.pipe(cleanCSS())
		.pipe(sourcemaps.write("./"))
		.pipe(gulp.dest("./static/css/"));
});

gulp.task("build-release-sass", () => {
	return gulp.src("./scss/index.scss")
		.pipe(sass().on("error", sass.logError))
		.pipe(concat("style.css"))
		.pipe(cleanCSS())
		.pipe(gulp.dest("./static/css/"));
});

async function cleanMaps() {
  const { deleteAsync } = await import('del');
  return deleteAsync(["./static/css/*.map"]);
}

gulp.task("clean-maps", cleanMaps);

gulp.task("build-release", gulp.series("build-release-sass", "clean-maps"));

gulp.task("watch", () => {
	gulp.watch("./scss/**/*.scss", gulp.series("sass-build"));
});
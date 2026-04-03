# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-03

### Added

- **Process center** — unified real-time progress page for all background operations (transcoding, audio, restore, scan) with per-task progress bar and cancel button
- **File rename** on the single-file page; title is now directly clickable to enter edit mode
- **Transcoded badge** in the media list for files that have already been processed
- **Real-time status labels** on media list rows reflecting the current operation in progress
- **File permission checks** before starting any operation; clear error notification when source file is not writable
- **Version display** in footer and on auth pages
- **Media library link** in navbar for quick access from any page
- **Alembic migrations** for schema management; `alembic upgrade head` runs automatically on startup

### Changed

- Audio progress indicators replaced with compact inline radial progress rings
- Toast notifications are now larger and support long wrapping text
- Buttons for restore and delete-backup are hidden while transcoding is active on that file
- Cancelled operations now correctly restore UI state for audio and restore controls

### Fixed

- 500 error on `/single` when file is missing or media info is unavailable
- Single-file page and process center links now use `file_id` instead of path (fixes lookups after rename/move)
- File rename inline layout broken after Bootstrap show() refactor

## [0.1.0] - 2026-04-01

Initial public release.

### Added

**Core**
- Media library scanner with ffprobe-based metadata extraction (codec, resolution, bitrate, audio tracks, duration, file size)
- SQLite database for persistent file records and operation history
- Scan result caching; incremental rescans update existing records
- Flask + Flask-SocketIO backend with real-time progress delivery to the browser

**Transcoding**
- Hardware-accelerated transcoding via NVIDIA NVENC, Intel QSV, AMD AMF, and VAAPI
- Automatic VAAPI device detection across `/dev/dri/renderD*` on multi-GPU systems
- Smart CUDA fallback: attempts full GPU pipeline first, automatically retries with CPU-assisted scaling on incompatible sources (e.g. BDRemux)
- CPU transcoding with H.264, H.265, VP9, and AV1 (libx264, libx265, libvpx-vp9, libaom-av1)
- CRF quality control, preset selection, and resolution downscaling
- Optional backup copy of original before transcoding; one-click restore from the Originals page
- Skip backup mode for network drives (`don't keep backup copy` checkbox)
- Per-file transcoding lock preventing concurrent audio operations on the same file
- Transcoding task queue panel (offcanvas sidebar) with per-task progress ring and stop button

**Audio track management**
- Extract individual audio tracks from video files (copy codec, preserves language/title metadata)
- Remove audio tracks from video files (remux in place)
- Add external audio tracks to video files with automatic sync (trim if longer, pad with silence if shorter)
- Audio track library page listing all extracted tracks

**UI**
- Responsive media library table powered by DataTables (search, sort, pagination)
- Per-file detail page with stream inspector, thumbnail strip, transcoding form, audio controls, and operation history
- Originals page for managing backup copies
- Configure page for directories and output paths
- Tokyo Night dark theme with JetBrains Mono font throughout
- Tab title animation during scan (`* scanning... mctl`)
- Transcoding progress reflected in browser tab title

**Auth**
- Username/password authentication with bcrypt hashing
- First-run registration flow (no pre-seeded credentials)
- Admin password reset via `config.json` flag

**Notifications**
- Persistent notification center (offcanvas sidebar) with unread badge on bell icon
- Real-time toast notifications for all background operations (transcoding, audio, scan, restore)
- Toast auto-dismiss after 5 s; hover pauses timer and marks notification as read
- Cross-tab badge synchronisation via BroadcastChannel API
- Per-notification delete; mark all read; clear all

**Infrastructure**
- SQLite connection lifecycle management via context manager (no file descriptor leaks)
- Thumbnail generation and cache invalidation on file change
- Transcoding savings statistics (files transcoded, bytes saved, percent reduction)
- `config.json` auto-generated from `config.example.json` on first run

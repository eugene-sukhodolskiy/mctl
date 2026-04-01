# mctl

A self-hosted media library manager with hardware-accelerated transcoding, audio track management, and a real-time web interface.

![License](https://img.shields.io/badge/license-GPL%20v3-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)

## Features

- **Media library browser** — scans configured directories, displays codec, resolution, bitrate, audio tracks, and file size for each file
- **Hardware-accelerated transcoding** — supports NVIDIA NVENC, Intel QSV, AMD AMF, and VAAPI with automatic device detection; smart CUDA fallback for incompatible source files
- **Audio track management** — extract, remove, and add audio tracks; external audio track library with per-file history
- **Original backups** — optionally keeps a backup copy of the original file before transcoding, with one-click restore
- **Notification center** — persistent in-app notifications for all background operations with real-time delivery via WebSockets
- **Operation history** — per-file log of all transcoding and audio operations
- **Thumbnail preview** — auto-generated thumbnails for each video file
- **Statistics** — tracks total files transcoded and disk space saved

## Requirements

For hardware acceleration:
- **NVIDIA**: CUDA-capable GPU with NVENC support
- **Intel**: VA-API or QSV-capable iGPU/dGPU
- **AMD**: VAAPI or AMF-capable GPU

## Installation

### Docker (recommended)

```bash
# 1. Clone the repository
git clone https://github.com/yourname/mctl.git
cd mctl

# 2. Create the data directory and copy the config
mkdir data
cp config.example.json data/config.json

# 3. Edit data/config.json — add your media directory paths
# 4. Mount them in docker-compose.yml (see Configuration below)

# 5. Build and run
docker compose up -d
```

Open [http://localhost:5000](http://localhost:5000). On first run you will be prompted to create an admin account.

### Manual (local development)

Requirements: Python 3.10+, [ffmpeg](https://ffmpeg.org/) and ffprobe in `PATH`, Node.js 18+ and npm.

```bash
# 1. Clone the repository
git clone https://github.com/yourname/mctl.git
cd mctl

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Node dependencies and build CSS
npm install
npm run build-release

# 5. Run
python app.py
```

Open [http://localhost:5000](http://localhost:5000).

## Configuration

`config.json` is automatically created from `config.example.json` on first run.

**For Docker**, place your config at `data/config.json` and mount your media directories in `docker-compose.yml`. Mount them at the same path as on the host so `config.json` requires no changes:

```yaml
volumes:
  - ./data:/data
  - /your/media-storage:/your/media-storage:ro
```

You can add as many mounts as needed:

```yaml
volumes:
  - ./data:/data
  - /mnt/disk1/films:/mnt/disk1/films:ro
  - /mnt/disk2/series:/mnt/disk2/series:ro
  - /home/user/media:/home/user/media:ro
```

```bash
docker compose down && docker compose up -d
```

Then reference the same paths in `data/config.json`:

```json
{
    "directories": [
        "/mnt/disk1/films",
        "/mnt/disk2/series",
        "/home/user/media"
    ],
    "cache_dir": "/data/cache",
    "transcoded_directory": "/data/transcoded_files",
    "audio_tracks_directory": "/data/audio-tracks"
}
```

**For local development**, paths can be relative or absolute:

```json
{
    "directories": ["/path/to/your/media"],
    "cache_dir": "cache",
    "transcoded_directory": "transcoded_files",
    "audio_tracks_directory": "audio-tracks"
}
```

| Key | Description |
|-----|-------------|
| `directories` | List of directories to scan for media files |
| `allowed_formats` | File extensions to include in the library |
| `cache_dir` | Directory for scan cache |
| `transcoded_directory` | Where backup copies of originals are stored before transcoding |
| `audio_tracks_directory` | Where extracted audio tracks are stored |

**Environment variables** (Docker / advanced):

| Variable | Default | Description |
|----------|---------|-------------|
| `MCTL_HOST` | `0.0.0.0` | Bind address |
| `MCTL_PORT` | `5000` | Listening port |
| `MCTL_DEBUG` | `false` | Enable Flask debug mode |
| `MCTL_DB_PATH` | `medialib.db` | Path to SQLite database file |
| `MCTL_CONFIG` | `config.json` | Path to config file |

## Frontend development

```bash
# Watch SCSS and rebuild on changes
npm run watch

# Production build
npm run build-release
```

## Tech stack

- **Backend**: Python, Flask, Flask-SocketIO, SQLite
- **Frontend**: Vanilla JS, Bootstrap 5, DataTables, Socket.IO client
- **Styling**: SCSS compiled via Gulp, Tokyo Night color theme, JetBrains Mono font
- **Media processing**: ffmpeg, ffprobe

## License

This project is licensed under the GNU General Public License v3.0 — see the [LICENSE](LICENSE) file for details.

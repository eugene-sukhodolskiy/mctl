import subprocess
import os
import glob
from db import update_operation, update_file_media_info, get_operation_by_id, mark_backup_deleted, get_file_by_path, calculate_and_save_stats
from mediascan import get_media_info_with_ffprobe
from thumbnails import invalidate_thumbs
from notifications import notify


def detect_available_accelerators():
    available = ["CPU"]

    # VAAPI — проверяем через vainfo на конкретных устройствах
    if _find_vaapi_device() is not None:
        available.append("VAAPI")

    # Intel QSV — требует Intel GPU + intel-media-sdk/oneVPL + ffmpeg с QSV
    if _has_intel_gpu() and _has_ffmpeg_hwaccel("qsv") and _has_ffmpeg_encoder("h264_qsv"):
        available.append("QSV")

    # NVENC — наличие NVIDIA устройства или nvidia-smi
    if os.path.exists("/dev/nvidia0") or _cmd_succeeds(["nvidia-smi", "-L"]):
        available.append("NVENC")

    # AMF — AMD GPU + ffmpeg скомпилирован с AMF (на Linux AMF экспериментальный)
    if _has_amd_gpu() and _has_ffmpeg_encoder("h264_amf"):
        available.append("AMF")

    return available


def _cmd_succeeds(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def _find_vaapi_device():
    """Возвращает путь к первому рабочему VAAPI render-устройству или None."""
    import glob as _glob
    for device in sorted(_glob.glob("/dev/dri/renderD*")):
        try:
            result = subprocess.run(
                ["vainfo", "--display", "drm", "--device", device],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                return device
        except Exception:
            # vainfo не установлен или устройство недоступно
            break
    # Fallback: vainfo без явного указания устройства
    if _cmd_succeeds(["vainfo"]):
        return "/dev/dri/renderD128"
    return None


def _has_ffmpeg_encoder(encoder_name):
    try:
        result = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                                capture_output=True, text=True, timeout=10)
        return encoder_name in result.stdout
    except Exception:
        return False


def _has_ffmpeg_hwaccel(accel_name):
    try:
        result = subprocess.run(["ffmpeg", "-hide_banner", "-hwaccels"],
                                capture_output=True, text=True, timeout=5)
        return accel_name in result.stdout
    except Exception:
        return False


def _has_intel_gpu():
    try:
        result = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return any(
                ("vga" in line or "display" in line or "3d controller" in line) and "intel" in line
                for line in result.stdout.lower().splitlines()
            )
    except Exception:
        pass
    return False


def _has_amd_gpu():
    try:
        result = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return any(
                ("vga" in line or "3d controller" in line) and ("amd" in line or "radeon" in line)
                for line in result.stdout.lower().splitlines()
            )
    except Exception:
        pass
    return False

def get_hardware_codec(software_codec, hardware_acceleration):
    codec_map = {
        "libx265": {
            "NVENC": "hevc_nvenc",
            "VAAPI": "hevc_vaapi",
            "QSV":   "hevc_qsv",
            "AMF":   "hevc_amf",
            "CPU":   "libx265"
        },
        "libx264": {
            "NVENC": "h264_nvenc",
            "VAAPI": "h264_vaapi",
            "QSV":   "h264_qsv",
            "AMF":   "h264_amf",
            "CPU":   "libx264"
        },
        "libaom-av1": {
            "NVENC": None,         # NVENC не поддерживает AV1 в большинстве сборок
            "VAAPI": "av1_vaapi",  # Intel Xe+, AMD RX 7000+
            "QSV":   "av1_qsv",   # Intel Arc+
            "AMF":   "av1_amf",   # AMD RX 7000+
            "CPU":   "libaom-av1"
        },
        "libvpx-vp9": {
            "NVENC": None,         # NVENC не поддерживает VP9
            "VAAPI": "vp9_vaapi", # Только Intel VAAPI; на AMD почти не работает
            "QSV":   None,         # QSV VP9 encode не поддерживается
            "AMF":   None,         # AMF VP9 encode не поддерживается
            "CPU":   "libvpx-vp9"
        }
    }

    # Проверка наличия кодека в таблице
    if software_codec not in codec_map:
        raise ValueError(f"Unsupported software codec: {software_codec}")
    if hardware_acceleration not in codec_map[software_codec]:
        raise ValueError(f"Unsupported hardware acceleration type: {hardware_acceleration}")

    # Получение аппаратного кодека
    hardware_codec = codec_map[software_codec][hardware_acceleration]
    if hardware_codec is None:
        return software_codec
    
    return hardware_codec

# Ошибка CUDA-фильтра при изменении параметров видеопотока (BDRemux и т.п.)
_NVENC_CUDA_FILTER_ERROR = "Impossible to convert between the formats supported by the filter"


def get_ffmpeg_transcoding_cmd(file_path, acceleration, codec, resolution, crf, preset, cpu_used, output_file, _nvenc_full_cuda=False):
    software_codec = codec
    codec = get_hardware_codec(software_codec, acceleration)
    if codec == software_codec:
        acceleration = "CPU"

    width = resolution

    hw_input_flags = []
    if acceleration == "VAAPI":
        vaapi_device = _find_vaapi_device() or "/dev/dri/renderD128"
        hw_input_flags = ["-vaapi_device", vaapi_device]
    elif acceleration == "NVENC":
        if _nvenc_full_cuda:
            # Полный CUDA-пайплайн: decode GPU → scale GPU → encode GPU
            hw_input_flags = ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
        else:
            # CPU-scale fallback: decode GPU → scale CPU → encode GPU
            hw_input_flags = ["-hwaccel", "cuda"]
    elif acceleration == "QSV":
        hw_input_flags = ["-hwaccel", "qsv"]
    # AMF: не требует hwaccel-флага на Linux — AMF SDK сам управляет устройством

    if acceleration == "VAAPI":
        vf = f"format=nv12,hwupload,scale_vaapi={width}:-2"
    elif acceleration == "NVENC" and _nvenc_full_cuda:
        vf = f"scale_cuda={width}:-2:passthrough=0:format=yuv420p"
    else:
        vf = f"scale={width}:-2"

    nvenc_preset_map = {
        "ultrafast": "p1", "superfast": "p1", "veryfast": "p2",
        "faster": "p3", "fast": "p4", "medium": "p5",
        "slow": "p6", "slower": "p7", "veryslow": "p7"
    }
    amf_preset_map = {
        "ultrafast": "speed", "superfast": "speed", "veryfast": "speed",
        "faster": "speed", "fast": "speed", "medium": "balanced",
        "slow": "quality", "slower": "quality", "veryslow": "quality"
    }

    if acceleration == "NVENC":
        quality_flag, quality_value = "-cq", str(crf)
    elif acceleration == "QSV":
        # global_quality — аналог CRF для Intel QSV (ICQ режим)
        quality_flag, quality_value = "-global_quality", str(crf)
    elif acceleration in ("VAAPI", "AMF"):
        quality_flag, quality_value = "-qp", str(crf)
    else:
        quality_flag, quality_value = "-crf", str(crf)

    command = ["ffmpeg"] + hw_input_flags + [
        "-i", file_path,
        "-map", "0:V",   # main video only (excludes attached pics / cover art)
        "-map", "0:a?",  # all audio streams
        "-map", "0:s?",  # all subtitle streams (optional)
        "-c:v", codec,
        "-vf", vf,
        "-c:a", "copy",
        "-c:s", "copy",
        quality_flag, quality_value
    ]

    av1_vp9_codecs = ["libaom-av1", "av1_vaapi", "av1_amf", "av1_qsv", "libvpx-vp9", "vp9_vaapi"]
    if codec in av1_vp9_codecs:
        command.extend(["-cpu-used", str(cpu_used)])
    elif acceleration == "NVENC":
        command.extend(["-preset", nvenc_preset_map.get(str(preset), "p4")])
    elif acceleration == "AMF":
        command.extend(["-quality", amf_preset_map.get(str(preset), "balanced")])
    elif acceleration in ("CPU", "QSV"):
        command.extend(["-preset", str(preset)])
    # VAAPI: пресеты не поддерживаются, не добавляем

    command.append(output_file)

    return command


def _run_ffmpeg_process(command, task, socketio, watch_cuda_error=False):
    """
    Запускает ffmpeg, эмитит progress-события.
    Возвращает (process, output_tail, cuda_error_detected).
    Если watch_cuda_error=True и обнаружена ошибка CUDA-фильтра —
    немедленно завершает процесс и возвращает cuda_error_detected=True.
    """
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    task["process"] = process

    output_tail = []
    cuda_error_detected = False

    for line in process.stdout:
        output_tail.append(line.rstrip())
        if len(output_tail) > 40:
            output_tail.pop(0)

        if watch_cuda_error and _NVENC_CUDA_FILTER_ERROR in line:
            cuda_error_detected = True
            process.terminate()
            break

        if "frame=" in line:
            socketio.emit('progress', {
                "task": {
                    "id": task["id"],
                    "file": task["file"],
                    "command": task["command"]
                },
                "message": line.strip()
            })

    process.wait()
    return process, output_tail, cuda_error_detected


def _copy_with_progress(src, dst, file_path, socketio, chunk_size=2 * 1024 * 1024):
    total = os.path.getsize(src)
    copied = 0
    with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
        while True:
            buf = fsrc.read(chunk_size)
            if not buf:
                break
            fdst.write(buf)
            copied += len(buf)
            percent = int(copied / total * 100)
            socketio.emit('copy-progress', {'file': file_path, 'percent': percent})
            socketio.sleep(0)  # yield to gevent event loop — file I/O is not patched by gevent


def transcode_file(transcoding_tasks, socketio, file_path, dest_path, acceleration, codec, resolution, crf, preset, cpu_used, operation_id=None, delete_original=False, user_id=None):
    # Phase 1: copy original to backup location
    if dest_path:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        socketio.emit('copy-progress', {'file': file_path, 'percent': 0})
        _copy_with_progress(file_path, dest_path, file_path, socketio)

    base, ext = os.path.splitext(file_path)
    output_file = base + '_transcoded' + ext

    if os.path.exists(output_file):
        os.remove(output_file)

    # Для NVENC: сначала пробуем полный CUDA-пайплайн, при ошибке — CPU-scale fallback
    nvenc = (acceleration == "NVENC")
    command = get_ffmpeg_transcoding_cmd(
        file_path, acceleration, codec, resolution, crf, preset, cpu_used, output_file,
        _nvenc_full_cuda=nvenc
    )
    fallback_command = get_ffmpeg_transcoding_cmd(
        file_path, acceleration, codec, resolution, crf, preset, cpu_used, output_file,
        _nvenc_full_cuda=False
    ) if nvenc else None

    print(" ".join(command))

    task = {
        "id": "id_" + str(len(transcoding_tasks) + 1),
        "file": file_path,
        "output": output_file,
        "command": command,
        "process": None
    }
    transcoding_tasks[task["id"]] = task

    # Запуск с мониторингом CUDA-ошибки
    process, output_tail, cuda_error = _run_ffmpeg_process(
        command, task, socketio, watch_cuda_error=nvenc
    )

    # CUDA-фильтр упал — переключаемся на CPU-scale и рестартуем
    if cuda_error and fallback_command:
        if os.path.exists(output_file):
            os.remove(output_file)

        print("NVENC CUDA filter error detected — retrying with CPU-assisted scaling")
        socketio.emit('progress', {
            "task": {"id": task["id"], "file": task["file"], "command": fallback_command},
            "message": "CUDA pipeline failed — retrying with CPU-assisted scaling..."
        })
        task["command"] = fallback_command
        process, output_tail, _ = _run_ffmpeg_process(
            fallback_command, task, socketio, watch_cuda_error=False
        )

    # Step 3: Replace the original file with the transcoded file
    file_name = os.path.basename(file_path)
    if process.returncode == 0:
        os.replace(output_file, file_path)

        if operation_id:
            update_operation(operation_id, "completed")
            fresh_info = get_media_info_with_ffprobe(file_path)
            if fresh_info:
                update_file_media_info(file_path, os.path.getsize(file_path), fresh_info)
            db_file = get_file_by_path(file_path)
            if db_file:
                invalidate_thumbs(db_file["id"])

            if delete_original:
                op = get_operation_by_id(operation_id)
                if op and op.get("backup_path") and os.path.exists(op["backup_path"]):
                    os.remove(op["backup_path"])
                mark_backup_deleted(operation_id)

        stats = calculate_and_save_stats()
        notify(socketio, user_id, "success", f"Transcoding complete: {file_name}",
               f"Codec: {codec} · Acceleration: {acceleration}")
        socketio.emit('completed', {
            "task": {
                "id": task["id"],
                "file": task["file"],
                "command": task["command"]
            },
            "message": f"File {file_path} transcoded successfully",
            "stats": stats
        })

        del transcoding_tasks[task["id"]]
    else:
        if task["id"] in transcoding_tasks:
            if operation_id:
                update_operation(operation_id, "failed")
            ffmpeg_log = "\n".join(output_tail[-20:]) if output_tail else ""
            notify(socketio, user_id, "error", f"Transcoding failed: {file_name}", ffmpeg_log or None)
            socketio.emit('error', {
                "task": {
                    "id": task["id"],
                    "file": task["file"],
                    "command": task["command"]
                },
                "message": f"Transcoding failed for {file_path}",
                "ffmpeg_log": ffmpeg_log
            })
            del transcoding_tasks[task["id"]]
        else:
            if operation_id:
                update_operation(operation_id, "canceled")
            socketio.emit('canceled', {
                "task": {
                    "id": task["id"],
                    "file": task["file"],
                    "command": task["command"]
                },
                "message": f"Transcoding canceled for {file_path}"
            })

        if os.path.exists(output_file):
            os.remove(output_file)
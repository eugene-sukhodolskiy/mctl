transcoding_tasks = {}
GStorage = {"scaning_state": "inaction"}

# Set by app.py during startup
socketio = None
config = {}
CONFIG_FILE = None
available_accelerators = []


def is_file_transcoding(file_path):
    return any(t.get("file") == file_path for t in transcoding_tasks.values())

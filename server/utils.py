import os


def check_writable(path):
    """Return an error string if path is not writable, else None."""
    if not os.path.exists(path):
        return f'File not found: {os.path.basename(path)}'
    if not os.access(path, os.W_OK):
        return f'No write permission: {os.path.basename(path)}'
    return None


def check_dir_writable(path):
    """Return an error string if directory is not writable, else None."""
    if not os.path.isdir(path):
        return f'Directory not found: {path}'
    if not os.access(path, os.W_OK):
        return f'No write permission on directory: {path}'
    return None

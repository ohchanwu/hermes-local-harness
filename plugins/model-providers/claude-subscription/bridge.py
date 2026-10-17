"""Client side of the MCP bridge."""
import json
import os


def save(path, value):
    """Atomic exclusive IPC write (the server has no authority over tool paths)."""
    temporary = path.with_name(path.name + ".writing")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

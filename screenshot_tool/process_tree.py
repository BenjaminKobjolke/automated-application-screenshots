"""Process-tree termination used by long-running child processes."""

from contextlib import suppress

import psutil


def kill_process_tree(pid: int) -> None:
    """Terminate a process and its descendants, retrying survivors once."""
    try:
        root = psutil.Process(pid)
        children = root.children(recursive=True)
    except psutil.NoSuchProcess:
        return
    for child in children:
        with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            child.kill()
    with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
        root.kill()
    gone, alive = psutil.wait_procs([*children, root], timeout=2)
    del gone
    for process in alive:
        with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            process.kill()

#!/usr/bin/env python3
"""Shared filesystem helpers."""

from __future__ import annotations

import contextlib
import fcntl
from pathlib import Path


@contextlib.contextmanager
def locked_file(path, exclusive=False):
    path = Path(path)
    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock_handle:
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(lock_handle.fileno(), mode)
        try:
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

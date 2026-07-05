"""
Unit tests for runtime lock behavior.
"""

from __future__ import annotations

import os

import pytest

from emergence.admin.paths import manifest_path, pid_path
from emergence.admin.runtime_lock import RuntimeLock, RuntimeLockError
from tests.helpers_admin import short_data_dir


@pytest.mark.unit
class TestRuntimeLock:
    def test_acquire_and_release_writes_and_clears_files(self, monkeypatch):
        data_dir = short_data_dir("lock1")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        lock = RuntimeLock.create()
        lock.acquire()
        lock.publish_manifest(host="127.0.0.1", port=9876)

        assert pid_path().exists()
        assert manifest_path().exists()
        assert int(pid_path().read_text().strip()) == os.getpid()

        manifest = manifest_path().read_text()
        assert "9876" in manifest

        lock.release()

        assert not pid_path().exists()
        assert not manifest_path().exists()

    def test_second_acquire_raises_while_runtime_alive(self, monkeypatch):
        data_dir = short_data_dir("lock2")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        lock = RuntimeLock.create()
        lock.acquire()

        other = RuntimeLock.create()
        with pytest.raises(RuntimeLockError, match="already running"):
            other.acquire()

        lock.release()

    def test_stale_pid_file_is_replaced(self, monkeypatch):
        data_dir = short_data_dir("lock3")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))
        pid_path().write_text("999999\n")

        lock = RuntimeLock.create()
        lock.acquire()
        assert int(pid_path().read_text().strip()) == os.getpid()
        lock.release()

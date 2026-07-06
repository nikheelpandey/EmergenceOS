from __future__ import annotations

from typing import Any

from emergence.core.ids import ProcessID
from emergence.tools.services import ToolServices
from emergence.tools.vfs import VirtualFilesystem


def create_fs_handlers(services: ToolServices, vfs: VirtualFilesystem):
    def read_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        path = str(args.get("path", "")).strip()
        if not path:
            raise ValueError("path required")
        space_id = args.get("space_id") or services.space_for_process(process_id)
        return vfs.read(space_id, path, encoding=str(args.get("encoding", "utf-8")))

    def write_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        path = str(args.get("path", "")).strip()
        if not path:
            raise ValueError("path required")
        if "content" not in args:
            raise ValueError("content required")
        space_id = args.get("space_id") or services.space_for_process(process_id)
        return vfs.write(
            space_id,
            path,
            str(args["content"]),
            encoding=str(args.get("encoding", "utf-8")),
        )

    def list_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        path = str(args.get("path", "."))
        space_id = args.get("space_id") or services.space_for_process(process_id)
        return vfs.list(space_id, path)

    def delete_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        path = str(args.get("path", "")).strip()
        if not path:
            raise ValueError("path required")
        space_id = args.get("space_id") or services.space_for_process(process_id)
        return vfs.delete(space_id, path)

    def stat_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        path = str(args.get("path", "")).strip()
        if not path:
            raise ValueError("path required")
        space_id = args.get("space_id") or services.space_for_process(process_id)
        return vfs.stat(space_id, path)

    return {
        "fs.read": read_handler,
        "fs.write": write_handler,
        "fs.list": list_handler,
        "fs.delete": delete_handler,
        "fs.stat": stat_handler,
    }

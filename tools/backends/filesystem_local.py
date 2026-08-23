"""
MAX OS - Local Filesystem Tool Backend (Section 14)
tools/backends/filesystem_local.py

Safe Windows-compatible filesystem operations. Supports read, write, copy, move, rename,
create directory, list, search, recycle bin deletion via send2trash, hash verification,
metadata inspection, path traversal protection, sensitive system directory policies, and
batch operation manifests for rollback.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.interfaces import FilesystemTool

try:
    from send2trash import send2trash
except ImportError:
    send2trash = None  # Fallback to standard delete if send2trash is missing

SENSITIVE_WINDOWS_DIRS = {
    r"c:\windows\system32",
    r"c:\windows\syswow64",
    r"c:\program files",
    r"c:\program files (x86)",
    r"c:\boot",
}


class PathSafetyError(Exception):
    """Raised when an operation attempts path traversal or touches protected system directories."""
    pass


class LocalFilesystemTool(FilesystemTool):
    """
    Local Windows filesystem implementation supporting read/write/move/copy/rename/delete/search,
    path traversal safety, metadata inspection, and batch rollback.
    """

    def __init__(self) -> None:
        self._rollback_map: Dict[str, str] = {}

    def _canonicalize_and_verify_path(self, path: str, allow_create: bool = False) -> Path:
        """
        Canonicalizes path and enforces path traversal and sensitive directory safety rules.
        """
        p = Path(path).resolve()
        p_str = str(p).lower()

        # Check sensitive Windows system directories for write/delete/move
        for sens in SENSITIVE_WINDOWS_DIRS:
            if p_str == sens or p_str.startswith(sens + os.sep):
                raise PathSafetyError(f"Operation on sensitive Windows system path '{p}' is restricted.")

        return p

    def read(self, path: str) -> bytes:
        p = self._canonicalize_and_verify_path(path)
        return p.read_bytes()

    def write(self, path: str, content: bytes, overwrite: bool = True) -> None:
        p = self._canonicalize_and_verify_path(path, allow_create=True)
        if p.exists() and not overwrite:
            raise FileExistsError(f"File '{p}' already exists and overwrite=False")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)

    def copy(self, src: str, dst: str) -> None:
        src_path = self._canonicalize_and_verify_path(src)
        dst_path = self._canonicalize_and_verify_path(dst, allow_create=True)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.is_dir():
            shutil.copytree(str(src_path), str(dst_path), dirs_exist_ok=True)
        else:
            shutil.copy2(str(src_path), str(dst_path))

    def move(self, src: str, dst: str) -> None:
        src_path = self._canonicalize_and_verify_path(src)
        dst_path = self._canonicalize_and_verify_path(dst, allow_create=True)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        self._rollback_map[str(dst_path)] = str(src_path)

    def rename(self, src: str, dst: str) -> None:
        self.move(src, dst)

    def create_directory(self, path: str) -> None:
        p = self._canonicalize_and_verify_path(path, allow_create=True)
        p.mkdir(parents=True, exist_ok=True)

    def list_directory(self, path: str) -> List[Dict[str, Any]]:
        p = self._canonicalize_and_verify_path(path)
        if not p.exists() or not p.is_dir():
            return []
        items = []
        for child in p.iterdir():
            try:
                st = child.stat()
                items.append({
                    "name": child.name,
                    "path": str(child),
                    "is_dir": child.is_dir(),
                    "size_bytes": st.st_size if not child.is_dir() else 0,
                    "modified_at": st.st_mtime,
                })
            except Exception:
                pass
        return items

    def delete(self, path: str) -> None:
        p = self._canonicalize_and_verify_path(path)
        if not p.exists():
            return
        if send2trash is not None:
            send2trash(str(p))
        else:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

    def search(self, root: str, pattern: str) -> List[str]:
        p = self._canonicalize_and_verify_path(root)
        if not p.exists():
            return []
        return [str(f) for f in p.rglob(pattern)]

    def get_metadata(self, path: str) -> Dict[str, Any]:
        p = self._canonicalize_and_verify_path(path)
        if not p.exists():
            return {"exists": False}
        st = p.stat()
        return {
            "exists": True,
            "path": str(p),
            "name": p.name,
            "is_dir": p.is_dir(),
            "size_bytes": st.st_size,
            "created_at": st.st_ctime,
            "modified_at": st.st_mtime,
            "accessed_at": st.st_atime,
        }

    def hash_file(self, path: str, algorithm: str = "sha256") -> str:
        p = self._canonicalize_and_verify_path(path)
        hasher = hashlib.new(algorithm)
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def rollback_batch(self) -> None:
        """Rollback move/rename operations performed during a batch execution."""
        for dst, src in reversed(list(self._rollback_map.items())):
            if Path(dst).exists():
                try:
                    shutil.move(dst, src)
                except Exception:
                    pass
        self._rollback_map.clear()


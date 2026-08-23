"""
MAX OS - Tool Interfaces
tools/interfaces.py

Agents call these interfaces, never OS implementation details directly.
This is what keeps the platform abstraction layer (core/platform/detector.py)
a clean seam instead of an if-else scattered through every agent. Each
concrete backend implements one of these and is selected at startup based on the CapabilityProfile.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class ComputerTool(ABC):
    @abstractmethod
    def move_mouse(self, x: int, y: int) -> None: ...

    @abstractmethod
    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> None: ...

    @abstractmethod
    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None: ...

    @abstractmethod
    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None: ...

    @abstractmethod
    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None: ...

    @abstractmethod
    def scroll(self, clicks: int = 3, direction: str = "down") -> None: ...

    @abstractmethod
    def type_text(self, text: str) -> None: ...

    @abstractmethod
    def press_keys(self, *keys: str) -> None: ...

    @abstractmethod
    def screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> bytes: ...

    @abstractmethod
    def list_windows(self) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def focus_window(self, window_id: str) -> bool: ...

    @abstractmethod
    def minimize_window(self, window_id: str) -> bool: ...

    @abstractmethod
    def maximize_window(self, window_id: str) -> bool: ...

    @abstractmethod
    def restore_window(self, window_id: str) -> bool: ...

    @abstractmethod
    def close_window(self, window_id: str) -> bool: ...


class BrowserTool(ABC):
    @abstractmethod
    def navigate(self, url: str) -> None: ...

    @abstractmethod
    def search(self, query: str) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def extract_text(self) -> str: ...

    @abstractmethod
    def click_selector(self, selector: str) -> bool: ...

    @abstractmethod
    def type_into(self, selector: str, text: str) -> bool: ...

    @abstractmethod
    def screenshot(self) -> bytes: ...


class FilesystemTool(ABC):
    @abstractmethod
    def read(self, path: str) -> bytes: ...

    @abstractmethod
    def write(self, path: str, content: bytes) -> None: ...

    @abstractmethod
    def copy(self, src: str, dst: str) -> None: ...

    @abstractmethod
    def move(self, src: str, dst: str) -> None: ...

    @abstractmethod
    def rename(self, src: str, dst: str) -> None: ...

    @abstractmethod
    def create_directory(self, path: str) -> None: ...

    @abstractmethod
    def list_directory(self, path: str) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def delete(self, path: str) -> None: ...

    @abstractmethod
    def search(self, root: str, pattern: str) -> List[str]: ...

    @abstractmethod
    def get_metadata(self, path: str) -> Dict[str, Any]: ...

    @abstractmethod
    def hash_file(self, path: str, algorithm: str = "sha256") -> str: ...


class TerminalTool(ABC):
    @abstractmethod
    def run(self, command: str, timeout: Optional[float] = None) -> CommandResult: ...


class CommandResult:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class SystemTool(ABC):
    @abstractmethod
    def cpu_usage(self) -> float: ...

    @abstractmethod
    def memory_usage(self) -> Dict[str, Any]: ...

    @abstractmethod
    def list_processes(self) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def network_status(self) -> Dict[str, Any]: ...


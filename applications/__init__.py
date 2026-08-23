"""
MAX OS — Application Adapters Package.
"""

from applications.base_adapter import BaseApplicationAdapter
from applications.browser_adapter import BrowserAdapter
from applications.file_explorer_adapter import FileExplorerAdapter
from applications.office_adapter import OfficeAdapter
from applications.terminal_adapter import TerminalAdapter
from applications.vscode_adapter import VSCodeAdapter

__all__ = [
    "BaseApplicationAdapter",
    "VSCodeAdapter",
    "BrowserAdapter",
    "FileExplorerAdapter",
    "TerminalAdapter",
    "OfficeAdapter",
]

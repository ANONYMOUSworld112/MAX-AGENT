"""
MAX OS — Windows System Adapter Implementation
"""

from src.system.adapters.linux import LinuxAdapter

class WindowsAdapter(LinuxAdapter):
    """Windows implementation extending LinuxAdapter fallback."""
    pass

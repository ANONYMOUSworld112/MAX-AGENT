"""
MAX OS — MacOS System Adapter Implementation
"""

from src.system.adapters.linux import LinuxAdapter

class MacOSAdapter(LinuxAdapter):
    """MacOS implementation extending LinuxAdapter fallback."""
    pass

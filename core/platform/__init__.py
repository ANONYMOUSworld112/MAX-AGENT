"""
MAX OS - Platform Detection Package
"""
from core.platform.detector import (
    CapabilityProfile,
    ControlLevel,
    DisplayServer,
    OSFamily,
    RiskLevel,
    detect_capability_profile,
)

__all__ = [
    "CapabilityProfile",
    "ControlLevel",
    "DisplayServer",
    "OSFamily",
    "RiskLevel",
    "detect_capability_profile",
]

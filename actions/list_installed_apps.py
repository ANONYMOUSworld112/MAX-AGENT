"""List app entries found in Windows Search, grouped by category."""

from core.app_registry import ApplicationRegistry

_REGISTRY = ApplicationRegistry()


def list_installed_apps(parameters=None, response=None, player=None, session_memory=None) -> str:
    groups = _REGISTRY.list_installed()
    if not _REGISTRY.inventory_available:
        return f"I couldn't read the Windows app inventory. {_REGISTRY.inventory_error}"
    if not groups:
        return "The Windows Search app inventory was checked, but it contained no app entries."

    lines = ["Apps found in the Windows Search inventory:"]
    for category, apps in groups.items():
        lines.append(f"\n{category} ({len(apps)}):")
        lines.extend(f"- {app.name}" for app in apps)
    return "\n".join(lines)


TOOL = {
    "name": "list_installed_apps",
    "description": "Reads the current Windows Search app inventory and lists the app entries it found by category.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    },
    "handler": list_installed_apps,
}

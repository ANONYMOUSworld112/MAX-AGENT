# Desktop UI

`ui.py` contains MAX's PyQt desktop interface and can be launched directly with `python ui.py`. The primary `python main.py` entry point also creates the UI and coordinates it with the live voice session.

`ui/components/` contains reusable task-list and task-progress widgets. UI startup and available controls depend on the host platform, display/audio devices, and installed dependencies. The README does not claim that the current UI has been exercised on every supported platform.

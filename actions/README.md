# Actions

`actions/` contains the built-in action handlers exposed to the live assistant. At startup, `core.action_loader` discovers Python modules that export a module-level `TOOL` declaration. Each declaration supplies the tool name, model-facing description, parameter schema, and handler.

## Main areas

- Desktop and keyboard control: `computer_control.py`, `computer_settings.py`, `desktop.py`, and `open_app.py`.
- Browser and web tasks: `browser_control.py` and `web_search.py`.
- File and code tasks: `file_controller.py`, `file_processor.py`, `code_helper.py`, and `dev_agent.py`.
- Other integrations: reminders, weather, media, flight search, messaging, monitoring, and installed-app discovery.

`main.py` includes the discovered action schemas with its live tool declarations and dispatches calls through the action registry. Action availability depends on the host platform, installed dependencies, configuration, and any required external credentials.

When adding an action, follow the `TOOL` shape and handler conventions described in `core/action_loader.py`. Keep parameters explicit and do not put credentials in source or tool metadata.

# VJIT keyboard input

Use the existing `computer_control` action for all code entry:

- `action: type` with the complete Java source in `text` types at the current caret.
- This action uses keyboard input and preserves existing editor contents.
- Do not use `smart_type`, `clear_field`, or `paste` for ordinary code entry.
- Do not send key-by-key macros. Newlines and indentation are part of the source text passed to `type`.
- If the editor or insertion point is uncertain, ask the user to focus the editor and position the caret before typing.

This file documents the keystroke route; it contains no credentials, personal data, or stored user code.

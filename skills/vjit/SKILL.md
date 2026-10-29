---
name: vjit
description: Writes Java solutions for user-provided problems and types the requested code into the active editor using keyboard input.
version: 1.0.0
action: computer_control
parameters:
  action:
    type: string
    description: Use type to enter generated Java source at the current caret.
  text:
    type: string
    description: Complete Java source code to type into the active editor.
preconditions:
  - The user asked for Java code to be typed or written into the active application.
  - A Java editor or code field is focused with the caret at the intended insertion point.
postconditions:
  - The requested Java source has been entered using keyboard input.
---

# VJIT Java coding and typing

Use this skill when the user asks for Java code for a problem and requests that MAX type or write the solution in the current application. The problem may be supplied in the conversation or visible in the active application.

1. Understand the problem, constraints, input/output format, and expected language level. If essential details are missing, ask a focused question before typing.
2. Produce a complete Java solution that matches the stated problem. Include the required class and entry point for the requested judge or project format. Keep the result to source code unless the user requests an explanation.
3. Ensure the intended editor is focused and the caret is at the requested insertion point. If the target is unclear, ask the user to focus the editor and place the caret.
4. Type the source with `computer_control` using `action: type` and the complete source in `text`. This sends keyboard input at the caret and preserves existing content.
5. Do not clear or replace the field, change windows, save files, run the code, or use the clipboard unless the user explicitly asks for that action.
6. Report briefly when typing finishes. Do not claim the code was compiled or tested unless that was actually requested and performed.

Follow [KEYSTROKES.md](KEYSTROKES.md) for the keyboard behavior and limits.

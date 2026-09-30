---
name: open_application
description: Launches an application or window on the desktop
version: 1.0.0
action: open_app
parameters:
  app_name:
    type: string
    description: The name or path of the application to launch
preconditions:
  - Application binary or alias exists
postconditions:
  - Application process or window is running
verification:
  verify: true
  verify_timeout: 2.0
---

# Open Application Skill

Launches desktop applications via the platform adapter and verifies process startup.

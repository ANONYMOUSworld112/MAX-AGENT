# VJIT-specific area

This directory is reserved for VJIT-specific, shareable configuration and documentation so those changes remain separate from MAX's shared code. The Java-problem typing behavior is defined in [`skills/vjit/SKILL.md`](../skills/vjit/SKILL.md), with its keyboard-input rules in [`skills/vjit/KEYSTROKES.md`](../skills/vjit/KEYSTROKES.md).

`config.example.yaml` is an inactive integration template (`enabled: false`). No VJIT service integration is currently implemented or configured here.

Do not commit credentials, student or staff records, or private institutional data. Keep secrets in local environment variables or an approved secret store, and keep private datasets outside Git.

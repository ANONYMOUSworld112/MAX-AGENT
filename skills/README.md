# Skills

`skills/` contains one directory per declarative skill. The existing `core.skill_loader.SkillLoader` parses `SKILL.md` files with YAML frontmatter and can dispatch a skill through an `ExecutionGateway` when called by a host.

- `open_application/` describes launching an application through the `open_app` action.
- `play_music/` describes a media playback task.
- `vjit/` contains Java-problem typing instructions and its keystroke guide. `main.py` appends these VJIT files to the live system prompt.

The skill loader is not referenced by the current `main.py` execution path; VJIT prompt loading is explicit. A skill file by itself does not add a new tool or action.

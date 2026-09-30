---
name: play_music
description: Controls media playback on the local audio output
version: 1.0.0
action: play_music
parameters:
  query:
    type: string
    description: Song title, artist, or URI
preconditions:
  - Audio device is available
postconditions:
  - Media session state is PLAYING
verification:
  verify: true
---

# Play Music Skill

Interacts with local media sessions to stream or play audio.

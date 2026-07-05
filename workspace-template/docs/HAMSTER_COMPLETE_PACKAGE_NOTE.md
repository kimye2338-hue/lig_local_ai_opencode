# Complete Hamster Pet package note

The ChatGPT session produced a complete local install ZIP named:

`OpenCodeLIG_Complete_Hamster_Pet_Overlay_20260705.zip`

SHA256:

`ce1a5565f2831bd819b6c65c898424065b5ec7e366368d136f2d31e627654f29`

The ZIP contains:

- animated hamster PNG frames extracted from the user-provided image
- `hamster_pet.ico`
- complete `agent_ops/ui/hamster_overlay.py`
- `agent_ops/status_writer.py`
- `launch/hamster.bat`
- `launch/hamster-test-status.bat`
- installer `INSTALL_COMPLETE_HAMSTER_PET.cmd.txt`
- `docs/FABLE_HAMSTER_CONNECT_PROMPT.md`

The GitHub connector used here can write UTF-8 text files but is not a normal git binary-file upload path. For final repository integration, Fable should either:

1. copy the files from the complete ZIP into the repository using normal git, or
2. use the provided docs/FABLE_HAMSTER_CONNECT_PROMPT.md to wire the runtime lifecycle first, then add the image assets from the ZIP.

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

GitHub connector limitation note:

The connector used in this session can write normal UTF-8 text files, but it is not the same as a full git binary-file upload workflow. The complete ZIP includes all binary PNG/ICO assets and the complete Windows overlay implementation. For final repository integration, Fable should copy the files from the ZIP into the repository using a normal git workflow, then wire `status_writer.py` into the existing OpenCodeLIG runtime.

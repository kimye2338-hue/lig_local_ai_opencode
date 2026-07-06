# naming-guide

## Goal

Make the repository look like a maintained engineering project, not a folder full of emergency final files.

## Rules

Use short, purpose-based names.

Prefer lowercase kebab-case for Markdown and batch wrappers.

Use snake_case for Python modules only when that is the existing project convention.

Avoid:

- final,
- real-final,
- latest,
- fixed,
- temp,
- new-new,
- v2/v3/v4 in active filenames,
- emotional or conversation-specific names,
- duplicate documents that describe the same thing.

Use dates only for archives or releases.

## Recommended active layout

```text
docs/
  official-facts.md
  design-review.md
  rebuild-plan.md
  diagnostics.md
  naming-guide.md
  prompt-research.md
  fable5-rebuild-prompt.md

launch/
  run.bat
  diag.bat
  repair.bat
  chrome.bat

scripts/
  install.py
  repair.py
  diagnose.py
  build-bundle.py
  check-tools.py

proxy/
  server.py
  README.md

browser/
  chrome.py
  README.md

ui/
  windows.py
  README.md

memory/
  README.md
  lessons/

diagnostics/
  README.md

archive/
  2026-07-02-old-installers/
```

## Migration principles

1. Do not move everything in one blind commit if import paths are fragile.
2. First add a map of old name to new name.
3. Move files by category.
4. Update references.
5. Run diagnostics.
6. Keep old files only in `archive/YYYY-MM-DD-description/`.
7. Do not keep duplicate “final” files in active folders.

## Examples

Bad:

```text
INSTALL_OPENCODELIG_V4_SIDE_OFFLINE_ALL_IN_ONE_WITH_SECRET_BOOTSTRAP_V3.bat.txt
PATCH_OPENCODELIG_OFFICIAL_TOOLS_FIX_V4.py.txt
V4_REVIEW_NOTES.md
real_final_installer_fixed.bat
```

Better:

```text
release/install.bat.txt
release/repair.py.txt
docs/design-review.md
docs/official-facts.md
archive/2026-07-02-installer-experiments/
```

## Rule of thumb

A new teammate should know what a file does from the name alone.

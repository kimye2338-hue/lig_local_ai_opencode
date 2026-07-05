# FABLE-PRODUCT-DIRECTION — build the product the user actually wants

## Status

READY

## Read first

- `docs/PRODUCT_VISION_AND_PROACTIVE_IMPLEMENTATION_20260705.md`
- `docs/COMPANY_PC_TRIALS_AND_NEXT_DIRECTION_20260705.md`
- `workspace-template/docs/MEMORY_AND_SELF_EXTENSION.md`
- `plan/tasks/FABLE-OCD-WORKSPACE-PROFILES.md`

## Goal

Implement OpenCodeLIG as a durable company-PC work automation assistant, not a narrow coding-only patch.

The user expects Fable to infer obvious missing support and add it when it is necessary for a feature to really work.

## Product assumptions

The program is for a Korean mechanical/design engineer using an internal Windows PC.

It should help with:

- browser/company portal automation,
- Office and HWP document work,
- Outlook work where allowed,
- SolidWorks, AutoCAD, MATLAB, and engineering-script workflows,
- report/document generation,
- local project work through `ocd`,
- durable global memory plus folder-local project memory.

## Implementation rules

For every user-facing feature, check:

1. Is the tool actually exposed to the LLM, not just implemented privately?
2. Does it work on Korean Windows paths and output?
3. Does it preserve global user memory?
4. Does it support project-local profile context where relevant?
5. Is there a diagnostic or doctor output?
6. Is there a minimal success test?
7. Does the user have a simple command to run?
8. Does it recover from common failure states?
9. Is the offline install path still simple and predictable?

## Near-term priorities

1. Finish and validate browser CDP tool exposure.
2. Implement `ocd` current-folder launcher and `.opencodelig` local profiles.
3. Inject global memory plus local persona/rules/project memory into agent context.
4. Add capability dashboard/doctor status for browser, memory, and project profiles.
5. Improve Windows command-output decoding so Korean CMD output is not garbled.
6. Add minimal proof tests for major adapters.
7. Later, add `ocd` templates for browser portal, Office report, SolidWorks macro, and general projects.

## Acceptance criteria

A patch is not done unless it includes the pieces needed for real use:

- implementation,
- LLM tool exposure when needed,
- tests or diagnostics,
- user-facing run instructions,
- memory-preservation check if memory or installer behavior is touched,
- handoff note explaining what changed and what remains.

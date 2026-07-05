# prompt-research

## Sources checked

- Anthropic Prompt engineering overview
- Anthropic Prompting Claude Fable 5
- Anthropic Prompting best practices
- Claude Code best practices
- Claude Code memory documentation
- Claude Code skills and hooks documentation

## Findings applied

### 1. Start with success criteria and evaluation

Anthropic's prompt engineering overview says prompt engineering should start after defining success criteria and ways to empirically test them. This changes the OpenCodeLIG prompt: it prioritizes observable Windows/internal-network behavior over preserving previous implementation.

### 2. Fable 5 should be given hard, ambiguous, long-horizon work

Anthropic's Fable 5 guidance says the model is strong on hard, long-running, ambiguous, end-to-end work. The revised prompt stops treating Fable as a narrow implementer and gives it authority to audit, discard, and redesign.

### 3. Use high effort, but avoid over-planning and unnecessary abstractions

Fable 5 guidance says effort controls intelligence/latency/cost, and high effort is appropriate for complex tasks. It also warns against over-planning and unnecessary cleanup. The revised prompt asks Fable to act once it has enough evidence and to avoid preserving old scaffolding.

### 4. Ground progress claims in actual tool results

Fable 5 guidance recommends auditing progress claims against tool results. The revised prompt requires evidence for claims, including tests, files, logs, and diagnostic outputs.

### 5. Use subagents and fresh-context verification

Claude Code best practices recommend verification subagents or separate evaluators for important checks. The revised prompt explicitly allows Fable to use verifier subagents.

### 6. Keep always-loaded instructions concise

Claude Code memory/best-practice guidance warns that bloated always-loaded instructions can reduce effectiveness. The revised prompt tells Fable to remove over-prescriptive instructions and use memory/skills selectively.

### 7. Explore first, then plan, then implement

Claude Code best practices recommend separating exploration/planning from implementation on uncertain multi-file work. The revised prompt requires an evidence-gathering phase before large architectural changes.

### 8. Use skills, hooks, and subagents only where they are actually valuable

Claude Code documentation recommends skills for domain workflows, hooks for deterministic actions, and subagents for isolated research. The revised prompt leaves implementation choices open rather than forcing the current skill/proxy design.

## Prompt-design changes made

Removed or softened:

- preserve V4,
- SAFE_PURE has no feature loss,
- always use this proxy,
- never use bash for file writing,
- must be single BAT,
- current skills layout is correct,
- Chrome automation must be stdlib CDP,
- UI automation must be scaffold-only.

Kept as facts:

- Windows target,
- internal network/offline reality,
- OpenAI-compatible internal API requirement,
- no secrets in public GitHub,
- antivirus false-positive sensitivity,
- core file automation goal,
- Korean user workflow.

Added:

- authority to discard architecture,
- runtime truth requirement,
- actual tools visibility diagnostics,
- repository naming cleanup,
- validation evidence requirement,
- concise final reporting requirement.

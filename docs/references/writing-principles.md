# Writing Principles for Codex Instruction Assets

Audience: Codex. Optimize for machine parsing, deterministic behavior, and verifiable outcomes.

## Core principles

1. **Be specific**
   - Name exact files, commands, and outputs.
   - Replace vague pronouns with explicit nouns.
2. **Define inputs and outputs**
   - List required context and what will be produced.
3. **Deterministic procedure**
   - Use numbered steps with clear control flow (if/then, stop conditions).
4. **Verification is required**
   - Include explicit checks and the commands to run (when applicable).
5. **Define failure modes**
   - State what to do when a precondition fails or a step cannot complete.
6. **State boundaries**
   - What is in scope; what is out of scope; what requires user approval.
7. **Economy**
   - Remove filler and redundancy; prefer active voice.

## Required sections (skills)

- Trigger / when to use
- Inputs
- Outputs
- Procedure
- Verification
- Failure modes
- Examples (happy path + edge case)

## Safety language

When actions might be destructive, require explicit approval and provide safer alternatives.

## Error format (scripts)

Use:

- `"{operation} failed: {reason}. Got: {input!r:.100}"`


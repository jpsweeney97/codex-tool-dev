# Example Skill

## Trigger / when to use

Use this skill when you need a deterministic example of a Codex skill structure for authoring new skills.

Do not use this skill to make changes in production environments.

## Inputs

- Repository working directory
- A target file path (optional)

## Outputs

- A short, structured response that includes procedure, verification, and failure modes.

## Procedure

1. Confirm the current working directory.
2. If a target file path is provided, check that it exists.
3. Describe the intended change in one sentence.
4. Provide a minimal set of actions to execute the change.

## Verification

- If code is modified, run the narrowest relevant test or command.
- If no test exists, provide an explicit manual verification checklist.

## Failure modes

- If the target file path does not exist, ask for the correct path.
- If required tools are missing, state what is missing and how to install it.

## Examples

### Happy path

Input: “Create a skill template for parsing logs.”

Output: Provide the required sections and a deterministic procedure.

### Edge case

Input: “Do it, but I won’t tell you which repo.”

Output: Ask for the working directory and constraints before proceeding.


# {{Skill Name}}

## Trigger / when to use

Use this skill when:

- {{Trigger condition 1}}
- {{Trigger condition 2}}

Do not use this skill when:

- {{Non-trigger condition 1}}

## Inputs

Required:

- {{Input 1}}
- {{Input 2}}

Optional:

- {{Optional input 1}}

## Outputs

Primary output:

- {{What success looks like / artifact produced}}

Secondary outputs (optional):

- {{Logs / report / diff summary}}

## Procedure

1. Preconditions
   - Confirm cwd and relevant files exist.
   - Confirm required tools are available.
2. Execute
   - Perform the smallest change that addresses the root cause.
3. Verify
   - Run the narrowest check first; broaden only if needed.
4. Report
   - Summarize what changed, what was verified, and any remaining risks.

## Verification

Commands (prefer the narrowest):

- `{{command}}`

Manual verification (if commands are unavailable):

- {{manual check 1}}
- {{manual check 2}}

## Failure modes

- If {{precondition}} fails: {{what to do / ask}}
- If {{tool}} is missing: {{install or fallback path}}
- If results are ambiguous: ask for clarification before proceeding.

## Examples

### Happy path

Input:

> {{example prompt}}

Expected behavior:

- {{expected step 1}}
- {{expected step 2}}

### Edge case

Input:

> {{edge-case prompt}}

Expected behavior:

- {{clarifying question or safe fallback}}


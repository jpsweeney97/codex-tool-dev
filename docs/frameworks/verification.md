# Verification Framework

Use this framework whenever a task changes code or state.

## Steps

1. **Preconditions**
   - Confirm cwd, relevant files, and tooling.
2. **Smallest change**
   - Make minimal edits to address the root cause.
3. **Run checks**
   - Prefer the most specific tests first, then broaden.
4. **Report results**
   - Provide commands run, outcomes, and remaining risks.
5. **Fallback**
   - If blocked, state what is missing and propose alternatives.


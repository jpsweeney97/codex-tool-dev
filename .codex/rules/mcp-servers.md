# Rules: MCP Servers

These rules are **blocking**. Read them before creating or editing any package under `packages/mcp-servers/`.

## Contract

- Must build from a clean checkout.
- Must document tools and required environment variables.
- Must include at least a smoke test.

## Safety

- Never hardcode secrets.
- Prefer read-only tools unless write access is explicitly required and gated.


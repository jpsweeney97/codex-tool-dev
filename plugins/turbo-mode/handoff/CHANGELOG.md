# Changelog

All notable changes to the Handoff plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This changelog begins at 3.2.1; earlier versions predate the file and are not reconstructed here.

## 3.2.2 - 2026-08-23

### Changed

- `throughline`: raised the size budget from ~32KB (~8k tokens) to ~64KB (~16k tokens), on both budget surfaces (`SKILL.md` Synthesis and `references/throughline-format.md` Size). The 32KB cap — introduced in 3.2.0 after the live throughline hit 98KB — was under active pressure (this repo's throughline sat at 31.5KB with 232 handoffs folded, forcing history compression on every refresh), and the 2026-07-03 methodology critique recorded that no measured failure anchored 32 specifically. 64KB doubles headroom while staying well below the 98KB size that motivated the original cap; load-handoff's full-read-per-session cost rises to ~16k tokens, judged acceptable. Compression rules and oldest-first order are unchanged.

## 3.2.1 - 2026-07-09

### Added

- `save-handoff`: added a secret-redaction discipline to `## What To Capture` — never transcribe API keys, passwords, tokens, connection strings, or personally identifiable information into a handoff; reference them by name or location instead. Handoffs are written to `.agents/handoffs/` and may be committed under host-repository policy, so a secret written into one can leak. Folded from mattpocock upstream (charter case-(d)) and routed through `agent-facing-design` (verdict: context-with-safe-default, not machinery — justified by the credential-exposure damage class, single-sourced to the writing skill, deliberately absent from `load-handoff` which never writes). Behavior forward-tested (Sonnet 5, secrets embedded in the session context, redaction never instructed): zero secrets transcribed verbatim, all non-secret facts preserved.

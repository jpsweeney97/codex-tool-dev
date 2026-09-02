# Relay Plugin Privacy Notice

This document describes the Relay plugin source package in this repository. It does not certify what any installed Codex runtime or plugin cache currently loads.

The Relay plugin provides instructions for carrying work between sessions by hand: composing paste packets and adjudicating replies (`courier`), staging sha-stamped packet files for sessions that share a filesystem (`relay-by-reference`), and writing commission prompts into a personal prompts repository (`stage-prompt`). It does not create background files, register hooks, run services, or intentionally transmit content to a separate service by itself.

Relay requests may cause the runtime to read local repository files, git state, pasted text, or other artifacts the user asks it to carry, and to write the files each skill documents: packet files under `~/scratch-workspace/relay/`, and prompt files under `~/prompts`, which `stage-prompt` commits and pushes to that repository's own remote. Packet and prompt bodies carry whatever the user chose to relay, so they may include file paths, quoted snippets, diffs, findings, and decisions.

Codex, Claude, account handling, model requests, telemetry, synchronization, and any host application behavior are governed outside this local plugin document.

Review a packet or prompt before carrying it to another session or model, especially when it may include private project details, file paths, customer data, credentials, or other sensitive information.

from __future__ import annotations

import pytest
from refresh.command_projection import extract_command_projection, has_semantic_policy_trigger


def test_projection_extracts_shell_blocks_and_command_lines() -> None:
    text = """# Command

```bash
python3 -B <PLUGIN_ROOT>/scripts/search.py query
```

uv run pytest tests/test_skill_docs.py -q
"""

    projection = extract_command_projection(text)

    assert "python3 -B <PLUGIN_ROOT>/scripts/search.py query" in projection.items
    assert "uv run pytest tests/test_skill_docs.py -q" in projection.items


def test_projection_preserves_shell_fence_non_comment_commands() -> None:
    text = """# Smoke

```shell
# inspect branch state
git status --short
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_skill_docs.py -q
```
"""

    projection = extract_command_projection(text)

    assert "git status --short" in projection.items
    assert "PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_skill_docs.py -q" in projection.items
    assert "# inspect branch state" not in projection.items


@pytest.mark.parametrize("fence", ['```bash title="smoke"', "``` bash"])
def test_projection_preserves_shell_fence_commands_with_info_strings(fence: str) -> None:
    text = f"""# Smoke

{fence}
git status --short
```
"""

    projection = extract_command_projection(text)

    assert "git status --short" in projection.items


def test_projection_extracts_untyped_command_blocks_and_json_payloads() -> None:
    text = """# Examples

```
codex plugin/read turbo-mode handoff
```

```json
{"request": "tool/execute", "action": "handoff.search", "query": "release"}
```
"""

    projection = extract_command_projection(text)

    assert "codex plugin/read turbo-mode handoff" in projection.items
    assert (
        '{"action":"handoff.search","query":"release","request":"tool/execute"}'
        in projection.items
    )


def test_projection_warns_on_malformed_json_payloads() -> None:
    text = """```json
{"request": "tool/execute", "action": }
```
"""

    projection = extract_command_projection(text)

    assert projection.items == ()
    assert projection.parser_warnings == ("json-payload-parse-failed",)


def test_projection_extracts_command_table_rows() -> None:
    text = """| Command | Action |
| --- | --- |
| `/load` | load handoff |
"""

    projection = extract_command_projection(text)

    assert "/load" in projection.items


def test_projection_extracts_command_header_table_cells() -> None:
    text = """| Command | Purpose |
| --- | --- |
| `plugin/read turbo-mode handoff` | inspect runtime inventory |
"""

    projection = extract_command_projection(text)

    assert "plugin/read turbo-mode handoff" in projection.items


def test_projection_extracts_longest_and_all_slash_commands() -> None:
    projection = extract_command_projection("Run /search, then /save and /load.\n")

    assert projection.items == ("/search", "/save", "/load")


def test_projection_ignores_generic_state_and_action_table() -> None:
    text = """| State | Action |
| --- | --- |
| open | update the owner |
"""

    projection = extract_command_projection(text)

    assert projection.items == ()


def test_semantic_policy_trigger_detects_runtime_authority_claim() -> None:
    assert has_semantic_policy_trigger(
        "Installed cache and runtime inventory authority changed during maintenance windows."
    )


def test_semantic_policy_trigger_ignores_plain_changelog_note() -> None:
    assert not has_semantic_policy_trigger("Fixed typo in heading and normalized capitalization.")

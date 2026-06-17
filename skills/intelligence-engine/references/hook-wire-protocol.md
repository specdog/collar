# Deepsuck Shell Hook Wire Protocol

Reference for building intelligence engine hook scripts. Extracted from `agent/shell_hooks.py`.

## Valid Hook Events

| Event | Fires | Can Block | Can Transform |
|-------|-------|-----------|---------------|
| `pre_tool_call` | Before any tool execution | Yes | No |
| `post_tool_call` | After tool execution | No | Yes (transform_tool_result) |
| `pre_llm_call` | Before LLM API call | No | Yes (inject context) |
| `post_llm_call` | After LLM response | No | Yes |
| `transform_llm_output` | Before returning to user | No | Yes (replace text) |
| `transform_tool_result` | On tool output | No | Yes (replace output) |
| `transform_terminal_output` | On terminal output specifically | No | Yes |
| `pre_api_request` | Before provider API call | No | Yes |
| `post_api_request` | After provider API response | No | Yes |
| `api_request_error` | On API error | No | Yes |
| `on_session_start` | Session initialization | No | No |
| `on_session_end` | Session teardown | No | No |
| `on_session_finalize` | Final session cleanup | No | No |
| `on_session_reset` | Session reset (/reset) | No | No |
| `subagent_start` | Subagent spawn | No | No |
| `subagent_stop` | Subagent completion | No | No |

## stdin Payload (all events)

```json
{
  "hook_event_name": "pre_llm_call",
  "tool_name": "terminal",
  "tool_input": {"command": "rm -rf /"},
  "session_id": "sess_abc123",
  "cwd": "/home/user/project",
  "extra": {}
}
```

- `hook_event_name`: always present, identifies the event
- `tool_name`: present for pre_tool_call, post_tool_call, transform_tool_result
- `tool_input`: the tool's arguments dict
- `session_id`: session identifier
- `cwd`: current working directory
- `extra`: event-specific kwargs

## stdout Response Shapes

### Block a tool call (pre_tool_call only)
```json
{"decision": "block", "reason": "Forbidden command"}
```
or
```json
{"action": "block", "message": "Forbidden command"}
```

### Inject context (pre_llm_call only)
```json
{"context": "### FRONTIER INTELLIGENCE PROTOCOL ACTIVE\n\nApply ToT + Reflexion..."}
```

### Transform output text (transform_llm_output)
```json
{"text": "<replacement text>"}
```

### Silent no-op
```json
{}
```
or any non-matching JSON object, or empty output.

## Config Format (config.yaml)

```yaml
hooks_auto_accept: true  # Skip TTY consent prompt

hooks:
  pre_llm_call:
    - command: python3 /path/to/hook.py
      timeout: 5        # seconds, max 300, default 60
      matcher: null      # regex for tool name (only pre/post_tool_call)
  
  transform_llm_output:
    - command: python3 /path/to/hook.py
      timeout: 5
  
  post_tool_call:
    - command: python3 /path/to/hook.py
      timeout: 3
  
  on_session_end:
    - command: python3 /path/to/hook.py
      timeout: 10
```

## Hook Script Template

```python
#!/usr/bin/env python3
import sys, json

if __name__ == "__main__":
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, IOError):
        payload = {}
    
    event = payload.get("hook_event_name", "")
    session_id = payload.get("session_id", "unknown")
    
    # Process based on event type
    if event == "pre_llm_call":
        # Inject context into system prompt
        print(json.dumps({"context": "Your injection here"}))
    elif event == "transform_llm_output":
        # Audit/transform output text
        text = payload.get("extra", {}).get("text", "")
        # ... process text ...
        print(json.dumps({"text": text}))
    elif event == "post_tool_call":
        # Side effects only (metrics, logging)
        # ... log metrics ...
        print(json.dumps({}))
    elif event == "on_session_end":
        # Generate reports
        print(json.dumps({}))
    else:
        # Unknown event — silent no-op
        print(json.dumps({}))
```

## Key Constraints

- **Execution time**: Keep hooks fast (<5s). They block the event pipeline. Max 300s.
- **subprocess.run**: Hooks use `shell=False` with `shlex.split()`. No shell injection.
- **Non-zero exit**: Logged as warning but stdout is still parsed for block/transform directives.
- **stderr**: Logged at DEBUG level. Not shown to user.
- **Allowlisting**: First-use consent gated by `~/.dag/shell-hooks-allowlist.json`. Use `hooks_auto_accept: true` to skip.
- **Idempotency**: Same (event, matcher, command) triple registers only once. Safe to call register_from_config() from both CLI and gateway.
- **Matcher field**: Only honored for `pre_tool_call` and `post_tool_call`. Regex matched against `tool_name`.

## CLI Commands

```bash
dag hooks list              # Show all configured hooks with status
dag hooks test <event>      # Fire hooks for <event> with synthetic payload
dag hooks doctor            # Check each hook: exec bit, allowlist, timing, JSON validity
dag hooks revoke <command>  # Remove allowlist entry (takes effect next restart)
```

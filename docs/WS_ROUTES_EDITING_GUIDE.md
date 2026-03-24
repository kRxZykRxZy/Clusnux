# WebSocket Routes: Read & Edit Guide

This guide is focused on quickly helping contributors read and edit code routes and WebSocket routes in Clusnux.

## Active files

- `cluster/network/websocket.py`
- `cluster/network/handling.py`
- `cluster/network/dameon.py` *(current filename in repository; keep as-is unless file is renamed in code)*

## Current route behavior

`handling.py` routes by `task`:

- `task="cmd"`:
  - starts process from `command`
  - stores process in `running_commands[pid]`
  - emits:
    - `cmd_started`
    - one or more `cmd_output`
    - `cmd_complete` or `cmd_error`
- `task="metrics"`:
  - collects CPU/memory/disk/network
  - emits `metrics` payload

## Message examples

### Run command

```json
{"task":"cmd","command":"echo hello"}
```

### Get metrics

```json
{"task":"metrics"}
```

## Add a new route

Edit `cluster/network/handling.py`:

```python
elif task == "route_name":
    # 1) parse/validate fields from data
    # 2) execute action
    # 3) send structured response
    await websocket.send(json.dumps({
        "task": "route_name",
        "status": "ok"
    }))
```

## Recommended new route keys

- `stop` (terminate by PID)
- `docker_run` (container execution)
- `tasks` (task module control)
- `admin_control` (privileged operations)
- `heartbeat` (node liveness)
- `logs` (log retrieval)

## Safety checklist when editing routes

- [ ] Always guard JSON parse errors in WS layer
- [ ] Validate required fields before executing actions
- [ ] Never trust command payloads without parsing
- [ ] Always remove finished PIDs from `running_commands`
- [ ] Keep response schema stable (`task`, `status`, IDs)
- [ ] Return machine-readable errors

## Common pitfalls

- Calling async handler without `await`
- Leaking processes when exceptions happen
- Sending mixed response formats that break admin clients
- Returning very large outputs in a single frame instead of streaming

## Testing recommendations

Because no test framework is currently configured in this repository, manually test with a WebSocket client:

1. Connect to node WebSocket endpoint
2. Send `{"task":"cmd","command":"echo hello"}`
3. Verify `cmd_started`, `cmd_output`, `cmd_complete`
4. Send `{"task":"metrics"}`
5. Verify metrics payload shape

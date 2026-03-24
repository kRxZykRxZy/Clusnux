# Clusnux Node Agent Architecture Design (CLI/Daemon + Admin Control)

This document provides a full **design blueprint** for evolving Clusnux into a Python-based, Kubernetes-style node agent system with administrator control.

> Scope note: this is a design and implementation guide for the current repository and future expansion. It documents how to read/edit current code routes and WebSocket routes, and how to scale to 150+ Python modules.

---

## 1) Goals

- Headless operation (CLI/daemon only)
- Linux + Windows compatibility
- Node daemon with persistent WebSocket server
- Admin/master remote control
- PID-based command execution + output streaming
- Metrics collection (CPU/RAM/Disk/Network + optional extras)
- Modular task system (tasks in isolated modules)
- Docker/container task execution
- Config-driven behavior (JSON/YAML)
- Security-aware admin access
- Scalable codebase structure (150+ Python modules)

---

## 2) Current Code Map (Repository Today)

- `cluster/network/dameon.py` *(current filename in repository; keep as-is unless file is renamed in code)*  
  Daemon wrapper that starts WebSocket worker thread.
- `cluster/network/websocket.py`  
  WebSocket server class and inbound message handler.
- `cluster/network/handling.py`  
  Request routing (`task` field), command execution, metrics response.

This is the active route flow at the moment:

1. daemon start
2. websocket message received
3. JSON decoded
4. request routed to `handle_request(...)`
5. route handler executes command/metrics behavior

---

## 3) WebSocket Route Contract (Current + Target)

Inbound frame format (JSON):

```json
{
  "task": "cmd",
  "command": "echo hello"
}
```

Primary route keys:

- `cmd` → run shell command, return PID, stream lines
- `metrics` → return metrics snapshot

Target routes to add/standardize:

- `stop` → terminate process by PID
- `docker_run` → run image/cmd via Docker
- `tasks` → start/stop/list modular tasks
- `admin_control` → privileged ops (restart, config update, kill task)
- `heartbeat` → node status ping
- `logs` → query log slice

Suggested outbound event schema:

```json
{
  "event": "cmd_output",
  "pid": 1255,
  "line": "build step 1 complete",
  "ts": "2026-03-24T19:18:12Z"
}
```

---

## 4) Read/Edit Guide for Code Routes and WS Routes

This section is for maintainers who need to safely modify command routes.

### 4.1 Files to edit

- WS transport and connection lifecycle:
  - `cluster/network/websocket.py`
- Route dispatch and command logic:
  - `cluster/network/handling.py`
- Daemon bootstrap:
  - `cluster/network/dameon.py` *(current filename in repository; keep as-is unless file is renamed in code)*

### 4.2 How to add a new WebSocket route

1. Open `cluster/network/handling.py`
2. Add a new `elif task == "<new_route>"` branch
3. Validate inputs from `data`
4. Return structured JSON via `await websocket.send(...)`
5. On failures, send an explicit `task`/`event` error payload

Example route skeleton:

```python
elif task == "logs":
    max_lines = int(data.get("max_lines", 200))
    await websocket.send(json.dumps({
        "task": "logs",
        "lines": [],
        "max_lines": max_lines
    }))
```

### 4.3 How to edit command route safely (`cmd`)

- Keep `shlex.split(cmd)` to avoid unsafe naive split logic.
- Track process handle in `running_commands[pid]`.
- Always clean up `running_commands.pop(pid, None)` in `finally`.
- Send lifecycle events in this order:
  1. `cmd_started`
  2. repeated `cmd_output`
  3. `cmd_complete` or `cmd_error`

### 4.4 How to add stop-by-PID route

Use tracked process map:

```python
elif task == "stop":
    pid = int(data["pid"])
    proc = running_commands.get(pid)
    if proc is None:
        await websocket.send(json.dumps({"task": "stop", "status": "not_found", "pid": pid}))
    else:
        proc.terminate()
        await websocket.send(json.dumps({"task": "stop", "status": "terminated", "pid": pid}))
```

### 4.5 WS route editing checklist

- [ ] JSON decode errors handled
- [ ] Missing-field validation exists
- [ ] PID/event naming stays consistent
- [ ] Route is fully async-safe (`await` used where needed)
- [ ] Error payloads are machine-readable
- [ ] No secrets returned in output

---

## 5) Proposed Scalable Project Layout (150+ Python Files Ready)

```text
cluster/
  node_agent/
    __init__.py
    main.py
    daemon/
      service.py
      lifecycle.py
      supervisor.py
      heartbeat.py
    transport/
      websocket_server.py
      websocket_session.py
      framing.py
      auth.py
      serializers/
        json_codec.py
        event_codec.py
    routing/
      dispatcher.py
      route_cmd.py
      route_metrics.py
      route_stop.py
      route_docker_run.py
      route_tasks.py
      route_admin_control.py
      route_logs.py
    execution/
      process_manager.py
      process_registry.py
      stream_pump.py
      shell_runner.py
      pid_guard.py
    metrics/
      collector.py
      cpu.py
      memory.py
      disk.py
      network.py
      process_table.py
      os_info.py
      battery.py
    tasks/
      registry.py
      task_runner.py
      dependencies.py
      catalog/
        task_001.py ... task_090.py
    containers/
      docker_client.py
      docker_runner.py
      image_validator.py
      templates/
        sample_task_container.py
    config/
      loader.py
      schema.py
      defaults.py
      hot_reload.py
      validators/
        auth_validator.py
        route_validator.py
    admin/
      control_client.py
      command_bus.py
      node_registry.py
      remote_config.py
      authn.py
      authz.py
    cli/
      main.py
      cmd_node.py
      cmd_tasks.py
      cmd_logs.py
      cmd_metrics.py
    logging/
      setup.py
      formatters.py
      rotation.py
      query.py
    persistence/
      sqlite_store.py
      state_repo.py
      migrations/
        migration_001.py ... migration_015.py
    security/
      token_service.py
      tls.py
      signatures.py
      audit.py
    utils/
      timeutil.py
      retry.py
      net.py
      platform.py
      ids.py
  tests/
    unit/
      test_routes_001.py ... test_routes_040.py
    integration/
      test_ws_001.py ... test_ws_020.py
    e2e/
      test_node_agent_001.py ... test_node_agent_010.py
```

The above pattern intentionally supports 150+ Python modules while remaining maintainable.

---

## 6) Example Implementation Snippets

### 6.1 Daemon entry point

```python
import asyncio
from cluster.node_agent.daemon.service import NodeDaemon

def main() -> None:
    daemon = NodeDaemon()
    asyncio.run(daemon.run_forever())

if __name__ == "__main__":
    main()
```

### 6.2 WebSocket server with PID tracking + streaming

```python
async def route_cmd(data, websocket, process_manager):
    cmd = data["command"]
    proc = await process_manager.start(cmd)
    await websocket.send({"event": "cmd_started", "pid": proc.pid})
    async for line in process_manager.stream(proc.pid):
        await websocket.send({"event": "cmd_output", "pid": proc.pid, "line": line})
    rc = await process_manager.wait(proc.pid)
    await websocket.send({"event": "cmd_complete", "pid": proc.pid, "returncode": rc})
```

### 6.3 Metrics reporting

```python
def collect_metrics() -> dict:
    return {
        "cpu_percent": cpu_percent(),
        "memory": memory_info(),
        "disk": disk_info(),
        "network": network_info(),
    }
```

### 6.4 Docker task execution

```python
async def route_docker_run(data, websocket, docker_runner):
    container_id = await docker_runner.run(
        image=data["image"],
        command=data.get("command")
    )
    await websocket.send({"event": "docker_run_started", "container_id": container_id})
```

### 6.5 Admin remote control interface

```python
async def route_admin_control(data, websocket, admin_service):
    action = data["action"]
    result = await admin_service.execute(action=action, payload=data)
    await websocket.send({"event": "admin_control", "result": result})
```

### 6.6 Modular task execution

```python
async def route_tasks(data, websocket, task_registry):
    task_name = data["name"]
    op = data.get("op", "start")
    result = await task_registry.execute(task_name, op=op, payload=data)
    await websocket.send({"event": "tasks", "name": task_name, "result": result})
```

---

## 7) Deployment Blueprint

- **Linux daemon**: systemd unit (`Restart=always`, environment file support)
- **Windows daemon**: run as Windows Service (pywin32/nssm wrapper)
- **EXE build**: PyInstaller onefile profile
  - `pyinstaller --onefile cluster/node_agent/main.py`
- **Docker support**: optional runtime for containerized tasks

---

## 8) Security Baseline

- Token-based admin authentication (JWT or signed opaque token)
- Optional mTLS between admin/master and node
- Route-level authorization for `admin_control`
- Audited commands and config changes
- Input validation for all WS payload fields

---

## 9) Extension Guidelines

- Add one route per module (`routing/route_*.py`)
- Keep transport layer thin; route logic in routing/service modules
- Avoid global state except explicit registries with locks
- Prefer async I/O for command execution and WebSocket handling

---

## 10) Documentation Coverage Plan

Documentation set should include:

- Architecture and data flow
- Node lifecycle and daemon behavior
- Route API reference (all WS routes)
- Admin operations manual
- Task authoring guide
- Configuration reference (JSON/YAML)
- Build/deploy guides (Linux/Windows/PyInstaller)
- Security hardening guide
- Troubleshooting and incident runbooks

See `docs/DOCS_BOOK_PLAN.md` for the 100+ page documentation plan and chapter placeholders.

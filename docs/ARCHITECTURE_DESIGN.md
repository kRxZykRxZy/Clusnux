# Clusnux Node Agent Architecture

This document captures a scalable architecture plan for the Clusnux Python node agent. It describes module boundaries, a module-ready folder layout, WebSocket command contracts, daemon/runtime behaviors, deployment targets, and a security baseline. Use this as the canonical reference when extending the agent.

## High-level overview

- **Daemon**: bootstraps the node, owns lifecycle, and hosts the WebSocket control surface.
- **WebSocket (WS)**: primary control plane used by administrators and orchestrators.
- **Admin**: privileged operations (node upgrade, controlled shutdown, log drains).
- **Tasks**: modular task runners (commands, scripts, containers, scheduled jobs).
- **Metrics**: local system telemetry (CPU, memory, disk, network) for orchestration.
- **Docker**: optional container lifecycle helpers for task isolation.
- **Logging**: structured, streaming logs for daemon and tasks.
- **Config**: immutable defaults + local overrides; supplies secrets via environment/volume.
- **CLI**: local operator entrypoint for starting/stopping the daemon and debugging.

## Module boundaries

| Module  | Responsibilities | Key interactions |
| --- | --- | --- |
| **daemon** | Process lifecycle, PID tracking, signal handling, WS server thread, health checks. | Spins up WS, wires config/logging, supervises tasks, exposes PID/state to admin. |
| **ws** | Accepts clients, parses/validates messages, routes to task/admin/metrics/docker handlers, streams outputs. | Uses task runners and metrics collectors; emits structured responses. |
| **admin** | Controlled shutdown, restart, upgrade hooks, configuration reload, log drains. | Uses daemon APIs and logging sinks; gated by authentication/authorization. |
| **tasks** | Executes commands/scripts, tracks per-task PID, supports cancellation/timeout and output streaming. | Called by WS routes; reports progress via WS events and logging. |
| **metrics** | Collects system metrics and task stats; exposes lightweight snapshot API. | Invoked by WS `metrics` route; feeds optional Prometheus/exporter. |
| **docker** | Pull/run/stop containers with resource limits; maps tasks into containers. | Called by WS `docker_run` and admin hooks; reuses logging and metrics. |
| **logging** | Structured JSON logs, task-scoped correlation IDs, rotate to disk/remote sinks. | Used by all modules; provides tail/stream to WS `logs` route. |
| **config** | Loads defaults, merges env/CLI flags, enforces schema, materializes secrets. | Consumed at daemon start; provides config objects to ws/tasks/docker/admin. |
| **cli** | Thin wrapper that starts/stops daemon, prints status/metrics, and issues WS commands locally. | Talks to daemon (local socket/WS) and reads config. |

## Module-ready folder layout (150+ capacity)

The layout below shows how to grow beyond 150 modules without deep refactors. New modules are added under the nearest vertical (e.g., `tasks/agents/agent_###`). Patterns, not every module, are enumerated to keep the tree concise.

```
cluster/
  daemon/
    __init__.py
    service.py           # PID file mgmt, signals, lifecycle
    supervisor.py        # health checks, restart policies
  network/
    websocket.py         # WS server + connection registry
    handling.py          # WS routing entrypoint
    schemas.py           # message schemas/validation
  admin/
    __init__.py
    control.py           # shutdown/restart/upgrade
    logs.py              # log drain/tail
  tasks/
    __init__.py
    runner.py            # command runner + streaming
    registry.py          # maps task names to handlers
    agents/
      agent_001/
      agent_002/
      ...
      agent_150/
      agent_template/    # scaffold for new modules
  metrics/
    __init__.py
    system.py            # CPU/mem/disk/net snapshots
    tasks.py             # per-task metrics
  docker/
    __init__.py
    runtime.py           # pull/run/stop with limits
    images.py            # image cache/policy
  logging/
    __init__.py
    config.py            # log format/sinks
    streams.py           # per-task streaming
  config/
    __init__.py
    loader.py            # env + file merge
    schema.py            # validation rules
  cli/
    __init__.py
    main.py              # start/stop/status commands
    ws_client.py         # local helper to hit WS routes
docs/
  ARCHITECTURE_DESIGN.md
  WS_ROUTES_EDITING_GUIDE.md
```

## WebSocket command contract & route patterns

All WS messages are JSON objects. Required fields must be validated before executing actions. Responses always include `task` and `status` plus identifiers (`pid`, `container_id`, `task_id`) when relevant.

| Task | Request fields | Response/event pattern |
| --- | --- | --- |
| `cmd` | `command` (string), optional `cwd`, `env`, `timeout` | `cmd_started` → repeated `cmd_output` (streamed lines) → `cmd_complete` or `cmd_error` |
| `metrics` | none | Single `metrics` payload with cpu/memory/disk/network snapshot |
| `stop` | `pid` | `stop_ack` on attempt, `stop_result` with outcome |
| `docker_run` | `image`, optional `command`, `env`, `mounts`, `limits` | `docker_started` → streamed `docker_output` → `docker_complete`/`docker_error` |
| `tasks` | `action` (`list`/`describe`), optional `task_id` | `tasks` payload or `task_info` |
| `admin_control` | `action` (`shutdown`/`restart`/`upgrade`), optional `reason` | `admin_ack` + follow-up status (`shutdown_scheduled`, etc.) |
| `heartbeat` | none | `heartbeat` reply with timestamp/node_id |
| `logs` | optional `pid` or `scope` | Streamed `log_line` events, followed by `logs_complete` |

### Contract notes

- Stream outputs in bounded frames to avoid large messages.
- Always remove finished PIDs from tracking maps (`running_commands`).
- Emit machine-readable errors with `status: "error"` and a short `code`.
- Reject unrecognized tasks with `{"status": "unsupported_task"}`.

## Daemon, PID tracking, streaming, and task modularity

- **Daemon thread**: the daemon launches the WS server in a dedicated thread with its own asyncio loop to avoid blocking the main process.
- **PID tracking**: every spawned process/container is registered in a PID (or container ID) map for cancellation and cleanup; entries are removed on completion/error.
- **Streaming**: command/container stdout is streamed line-by-line as discrete WS events; stderr is folded into the same stream unless the caller requests split channels.
- **Task modularity**: task handlers live in `tasks/registry.py` and `tasks/agents/...`; the WS layer delegates by task name so new handlers can be added without touching the WS server.
- **Deployment targets**: run as a systemd service, a container (Docker/K8s DaemonSet), or a bare-metal process; PID file and health endpoints enable supervision.

## Security baseline

- Prefer mutual TLS or a pre-shared token on WS connections; reject unauthenticated clients.
- Validate and sanitize all `command` and docker parameters; enforce allowlists for admin actions.
- Run tasks with least privilege (dedicated user/namespace/cgroup) and apply resource limits for CPU/memory/PIDs.
- Do not log secrets; redact sensitive fields before emitting log lines or metrics.
- Apply backpressure: cap concurrent tasks and drop/timeout idle WS connections.

## Practical guidance for reading/editing code and WS routes

- WS entrypoints live in `cluster/network/websocket.py` (server) and `cluster/network/handling.py` (routing/handlers). The daemon thread is in `cluster/network/daemon.py`.
- When adding a route:
  1) Parse + validate JSON early.  
  2) Route by `task` string in `handling.py`.  
  3) Stream outputs via `websocket.send` with consistent event names.  
  4) Remove PIDs/IDs from tracking maps on completion.  
  5) Add the contract to this document and `docs/WS_ROUTES_EDITING_GUIDE.md`.
- Keep responses stable; prefer additive changes. See `docs/WS_ROUTES_EDITING_GUIDE.md` for hands-on examples and tips.

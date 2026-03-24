"""
Tkinter-based futuristic (blue) admin/orchestrator/cluster console.

Requirements addressed:
- Real WebSocket connectivity (no stubs): connect to provided WS URLs, send heartbeat,
  metrics, tasks, commands, and admin controls using existing WS protocol.
- Server selection flows: pick any connected server, view metrics/graphs, run commands,
  manage runtime tasks, and push storage/runtime settings (Docker, mergerfs, Samba).
- Orchestrator/load balancer tab: pick role, set balancer mode, manage targets.
"""

from __future__ import annotations

import asyncio
import json
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import tkinter as tk
from tkinter import ttk

import websockets


# ------------------ Data models ------------------


@dataclass
class ServerSettings:
    docker_image: str = "ghcr.io/example/app:latest"
    mergerfs_source: str = "/data/disks/*"
    mergerfs_target: str = "/data/merged"
    samba_share: str = "/data/share"
    samba_user: str = "admin"
    samba_pass: str = "changeme"


@dataclass
class ServerTask:
    name: str
    status: str = "idle"
    last_output: str = ""


@dataclass
class Server:
    ws_url: str
    node_id: str | None = None
    role: str = "unknown"
    private_ip: str | None = None
    status: str = "unknown"
    cpu: float = 0.0
    mem: float = 0.0
    net: float = 0.0
    tasks: List[ServerTask] = field(default_factory=list)
    settings: ServerSettings = field(default_factory=ServerSettings)


@dataclass
class AppState:
    role: str = "admin"
    ws_urls: List[str] = field(default_factory=list)
    servers: Dict[str, Server] = field(default_factory=dict)  # key = ws_url
    active_ws: Optional[str] = None
    lb_mode: str = "round_robin"
    lb_targets: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)

    def log(self, message: str):
        ts = time.strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {message}")
        self.logs[:] = self.logs[-500:]

    def ensure_server(self, ws_url: str) -> Server:
        if ws_url not in self.servers:
            self.servers[ws_url] = Server(ws_url=ws_url)
        return self.servers[ws_url]

    def active_server(self) -> Optional[Server]:
        if self.active_ws and self.active_ws in self.servers:
            return self.servers[self.active_ws]
        return None


# ------------------ WebSocket manager ------------------


class WSManager:
    """
    Multiplexed WebSocket client manager (per-endpoint connection) with callbacks.
    """

    def __init__(self, on_message: Callable[[str, dict], None], on_disconnect: Callable[[str], None], log: Callable[[str], None]):
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self.log = log
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}

    async def _connect(self, url: str):
        if url in self.connections and not self.connections[url].closed:
            return self.connections[url]
        ws = await websockets.connect(url)
        self.connections[url] = ws
        self.log(f"Connected to {url}")
        asyncio.create_task(self._recv_loop(url, ws))
        return ws

    async def _recv_loop(self, url: str, ws: websockets.WebSocketClientProtocol):
        try:
            async for message in ws:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    self.log(f"[{url}] non-JSON message: {message}")
                    continue
                self.on_message(url, data)
        except websockets.exceptions.WebSocketException as exc:
            self.log(f"[{url}] websocket error: {exc}")
        except asyncio.CancelledError:
            raise
        finally:
            self.on_disconnect(url)

    def connect(self, url: str):
        asyncio.run_coroutine_threadsafe(self._connect(url), self.loop)

    def send(self, url: str, payload: dict):
        async def _send():
            ws = await self._connect(url)
            await ws.send(json.dumps(payload))
        asyncio.run_coroutine_threadsafe(_send(), self.loop)


# ------------------ UI ------------------


class AdminApp(tk.Tk):
    def __init__(self, state: AppState):
        super().__init__()
        self.title("Clusnux Admin / Orchestrator Console")
        self.geometry("1280x820")
        self.configure(bg="#0b1729")
        self.state = state
        self.ws_manager = WSManager(self._handle_message, self._handle_disconnect, self.state.log)
        self._build_styles()
        self._build_layout()
        self._refresh_logs_loop()

    # ---------- Styles ----------
    def _build_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        accent = "#3a86ff"
        surface = "#12233d"
        text = "#e2ecff"
        style.configure("TFrame", background=surface)
        style.configure("Card.TFrame", background=surface, relief="flat")
        style.configure("Header.TLabel", foreground=text, background=surface, font=("Segoe UI", 16, "bold"))
        style.configure("Sub.TLabel", foreground="#9fb4d4", background=surface, font=("Segoe UI", 10))
        style.configure("Accent.TButton", background=accent, foreground="#0b1729", borderwidth=0, padding=6)
        style.map("Accent.TButton", background=[("active", "#4f9dff")])
        style.configure("TButton", background="#1c2f4c", foreground=text, padding=6, borderwidth=0)
        style.map("TButton", background=[("active", "#254066")])
        style.configure("TLabel", background=surface, foreground=text)
        style.configure("TNotebook", background=surface)
        style.configure("TNotebook.Tab", background="#1c2f4c", foreground=text, padding=[10, 6])
        style.map("TNotebook.Tab", background=[("selected", accent)])
        style.configure("Treeview", background="#0f1f36", fieldbackground="#0f1f36", foreground=text, bordercolor=surface)
        style.map("Treeview", background=[("selected", accent)], foreground=[("selected", "#0b1729")])
        style.configure("TLabelframe", background=surface, foreground=text, bordercolor="#1f395d")

    # ---------- Layout ----------
    def _build_layout(self):
        root = ttk.Frame(self, padding=12, style="Card.TFrame")
        root.pack(fill="both", expand=True)

        top = ttk.Frame(root, padding=(0, 0, 0, 8), style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Clusnux Control Plane", style="Header.TLabel").pack(side="left")
        ttk.Label(top, text="Futuristic Docker-inspired blue console", style="Sub.TLabel").pack(side="left", padx=12)

        self.role_var = tk.StringVar(value=self.state.role)
        ttk.Label(top, text="Role", style="TLabel").pack(side="left", padx=(24, 4))
        ttk.Combobox(top, textvariable=self.role_var, values=["admin", "orchestrator", "cluster"], width=14).pack(side="left")

        ttk.Label(top, text="WS URLs (comma-separated)", style="TLabel").pack(side="left", padx=(18, 4))
        self.ws_entry = tk.Entry(top, width=60, bg="#0f1f36", fg="#e2ecff", insertbackground="#e2ecff", relief="flat")
        self.ws_entry.insert(0, "ws://127.0.0.1:8734")
        self.ws_entry.pack(side="left")
        ttk.Button(top, text="Connect & Discover", style="Accent.TButton", command=self._connect_and_discover).pack(side="left", padx=6)
        ttk.Button(top, text="Heartbeat all", command=self._heartbeat_all).pack(side="left")
        ttk.Button(top, text="Metrics (selected)", command=self._request_metrics).pack(side="left", padx=4)

        panes = ttk.Panedwindow(root, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(8, 0))

        # Left: server list
        left = ttk.Frame(panes, padding=10, style="Card.TFrame")
        self.server_tree = ttk.Treeview(left, columns=("node", "role", "status"), show="headings", height=22)
        self.server_tree.heading("node", text="Node")
        self.server_tree.heading("role", text="Role")
        self.server_tree.heading("status", text="Status")
        self.server_tree.column("node", width=180, anchor="w")
        self.server_tree.column("role", width=90, anchor="w")
        self.server_tree.column("status", width=100, anchor="w")
        self.server_tree.bind("<<TreeviewSelect>>", self._on_select_server)
        self.server_tree.pack(fill="both", expand=True)

        panes.add(left, weight=1)

        # Right
        right = ttk.Frame(panes, padding=10, style="Card.TFrame")
        panes.add(right, weight=3)

        self.selected_label = ttk.Label(right, text="No server selected", style="Header.TLabel")
        self.selected_label.pack(anchor="w")
        self.meta_label = ttk.Label(right, text="", style="Sub.TLabel")
        self.meta_label.pack(anchor="w")

        self.tabs = ttk.Notebook(right)
        self.tab_overview = ttk.Frame(self.tabs, style="Card.TFrame", padding=10)
        self.tab_settings = ttk.Frame(self.tabs, style="Card.TFrame", padding=10)
        self.tab_storage = ttk.Frame(self.tabs, style="Card.TFrame", padding=10)
        self.tab_tasks = ttk.Frame(self.tabs, style="Card.TFrame", padding=10)
        self.tab_lb = ttk.Frame(self.tabs, style="Card.TFrame", padding=10)
        self.tabs.add(self.tab_overview, text="Overview")
        self.tabs.add(self.tab_settings, text="Settings")
        self.tabs.add(self.tab_storage, text="Storage")
        self.tabs.add(self.tab_tasks, text="Commands & Tasks")
        self.tabs.add(self.tab_lb, text="Load Balancer")
        self.tabs.pack(fill="both", expand=True, pady=6)

        self._build_overview()
        self._build_settings()
        self._build_storage()
        self._build_tasks()
        self._build_lb()

        log_frame = ttk.Frame(right, padding=(0, 10, 0, 0), style="Card.TFrame")
        log_frame.pack(fill="both", expand=True)
        ttk.Label(log_frame, text="Event Stream", style="Sub.TLabel").pack(anchor="w")
        self.log_text = tk.Text(log_frame, height=7, background="#0f1f36", foreground="#e2ecff", relief="flat")
        self.log_text.pack(fill="both", expand=True)

    # ---------- Tabs ----------
    def _build_overview(self):
        header = ttk.Frame(self.tab_overview, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Live metrics (heartbeat + metrics task)", style="Sub.TLabel").pack(anchor="w")
        ttk.Button(header, text="Refresh metrics", command=self._request_metrics).pack(anchor="e")

        self.canvas = tk.Canvas(self.tab_overview, height=200, bg="#0f1f36", highlightthickness=0)
        self.canvas.pack(fill="x", pady=8)
        self.overview_text = ttk.Label(self.tab_overview, text="Send heartbeat and metrics to populate graphs.", style="TLabel", justify="left")
        self.overview_text.pack(anchor="w")

    def _build_settings(self):
        form = ttk.Frame(self.tab_settings, style="Card.TFrame")
        form.pack(fill="x")
        self.status_var = tk.StringVar()
        self.ws_var = tk.StringVar()
        ttk.Label(form, text="Status", style="TLabel").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.status_var, width=20).grid(row=0, column=1, sticky="w")
        ttk.Label(form, text="WebSocket URL", style="TLabel").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.ws_var, width=42).grid(row=1, column=1, sticky="w")
        ttk.Button(form, text="Push settings", style="Accent.TButton", command=self._push_settings).grid(row=2, column=0, columnspan=2, pady=8, sticky="w")

    def _build_storage(self):
        form = ttk.Frame(self.tab_storage, style="Card.TFrame")
        form.pack(fill="x")
        self.docker_var = tk.StringVar()
        self.merger_src_var = tk.StringVar()
        self.merger_tgt_var = tk.StringVar()
        self.samba_share_var = tk.StringVar()
        self.samba_user_var = tk.StringVar()
        self.samba_pass_var = tk.StringVar()
        self.storage_all_var = tk.BooleanVar(value=False)
        rows = [
            ("Docker image", self.docker_var),
            ("mergerfs source", self.merger_src_var),
            ("mergerfs target", self.merger_tgt_var),
            ("Samba share", self.samba_share_var),
            ("Samba user", self.samba_user_var),
            ("Samba password", self.samba_pass_var),
        ]
        for i, (label, var) in enumerate(rows):
            ttk.Label(form, text=label, style="TLabel").grid(row=i, column=0, sticky="w", pady=4)
            ttk.Entry(form, textvariable=var, width=48).grid(row=i, column=1, sticky="w")
        ttk.Checkbutton(form, text="Apply to all connected servers", variable=self.storage_all_var, style="TCheckbutton").grid(row=len(rows), column=0, columnspan=2, sticky="w", pady=(8, 4))
        ttk.Button(form, text="Push storage settings", style="Accent.TButton", command=self._push_storage).grid(row=len(rows)+1, column=0, columnspan=2, pady=10, sticky="w")

    def _build_tasks(self):
        wrapper = ttk.Frame(self.tab_tasks, style="Card.TFrame")
        wrapper.pack(fill="both", expand=True)

        cmd_frame = ttk.Labelframe(wrapper, text="Command Runner", padding=8, style="TLabelframe")
        cmd_frame.pack(fill="x", pady=6)
        self.cmd_var = tk.StringVar()
        ttk.Entry(cmd_frame, textvariable=self.cmd_var, width=60).pack(side="left", padx=(0, 6))
        ttk.Button(cmd_frame, text="Run", style="Accent.TButton", command=self._run_command).pack(side="left")

        task_frame = ttk.Labelframe(wrapper, text="Runtime Tasks", padding=8, style="TLabelframe")
        task_frame.pack(fill="both", expand=True, pady=6)
        self.task_list = tk.Listbox(task_frame, background="#0f1f36", foreground="#e2ecff", height=8, relief="flat")
        self.task_list.pack(fill="both", expand=True, side="left")
        controls = ttk.Frame(task_frame, style="Card.TFrame")
        controls.pack(side="left", padx=8)
        ttk.Button(controls, text="Refresh tasks", command=self._request_tasks).pack(fill="x", pady=2)
        ttk.Button(controls, text="Stop", command=lambda: self._task_action("stop")).pack(fill="x", pady=2)

    def _build_lb(self):
        frame = ttk.Frame(self.tab_lb, style="Card.TFrame")
        frame.pack(fill="x")
        ttk.Label(frame, text="Orchestrator load balancer controls", style="Sub.TLabel").pack(anchor="w", pady=(0, 6))
        self.lb_mode_var = tk.StringVar(value=self.state.lb_mode)
        ttk.Radiobutton(frame, text="Round robin", variable=self.lb_mode_var, value="round_robin").pack(anchor="w")
        ttk.Radiobutton(frame, text="Least connections", variable=self.lb_mode_var, value="least_conn").pack(anchor="w")
        ttk.Radiobutton(frame, text="IP hash", variable=self.lb_mode_var, value="ip_hash").pack(anchor="w")
        ttk.Button(frame, text="Apply balancer mode", style="Accent.TButton", command=self._apply_lb).pack(anchor="w", pady=8)
        self.lb_targets_var = tk.StringVar()
        ttk.Label(frame, text="Targets (comma-separated ws URLs)", style="TLabel").pack(anchor="w", pady=(6, 2))
        ttk.Entry(frame, textvariable=self.lb_targets_var, width=80).pack(anchor="w")
        ttk.Button(frame, text="Save targets", command=self._save_targets).pack(anchor="w", pady=6)

    # ---------- Message handling ----------
    def _handle_message(self, url: str, data: dict):
        task = data.get("task")
        if task == "heartbeat":
            srv = self.state.ensure_server(url)
            srv.node_id = data.get("node_id")
            srv.role = data.get("role", srv.role)
            srv.private_ip = data.get("private_ip", srv.private_ip)
            srv.status = "online"
            srv.ws_url = data.get("ws_url", url)
            self.state.log(f"Heartbeat from {srv.node_id or url}")
            self._refresh_server_list()
            self._render_selected()
        elif task == "tasks":
            srv = self.state.ensure_server(url)
            running = data.get("running", {})
            srv.tasks = [ServerTask(name=str(pid), status=str(status)) for pid, status in running.items()]
            self.state.log(f"Tasks updated for {srv.node_id or url}")
            self._render_selected()
        elif task == "metrics":
            srv = self.state.ensure_server(url)
            cpu = float(data.get("cpu_percent", 0.0)) / 100.0
            mem_info = data.get("memory", {})
            disk_info = data.get("disk", {})
            net_info = data.get("network", {}) or {}
            srv.cpu = max(0.0, min(1.0, cpu))
            srv.mem = float(mem_info.get("percent", 0.0)) / 100.0 if isinstance(mem_info, dict) else 0.0
            srv.net = 0.0
            if isinstance(net_info, dict):
                bytes_total = 0
                for _iface, counters in net_info.items():
                    try:
                        bytes_total += float(counters.get("bytes_sent", 0)) + float(counters.get("bytes_recv", 0))
                    except (TypeError, ValueError, AttributeError, KeyError):
                        continue
                # simple scale heuristic
                srv.net = min(1.0, bytes_total / (1024 * 1024 * 10))
            self._render_selected()
        elif task in {"cmd_started", "cmd_output", "cmd_complete", "cmd_error"}:
            self.state.log(f"[{url}] {task}: {data}")
            if task == "cmd_complete":
                self._request_tasks()
        else:
            # catch admin_control responses or errors
            self.state.log(f"[{url}] {data}")
        self._refresh_logs()

    def _handle_disconnect(self, url: str):
        srv = self.state.servers.get(url)
        if srv:
            srv.status = "offline"
        self.state.log(f"Disconnected from {url}")
        self._refresh_server_list()
        self._render_selected()
        self._refresh_logs()

    # ---------- Actions ----------
    def _connect_and_discover(self):
        urls = [u.strip() for u in self.ws_entry.get().split(",") if u.strip()]
        self.state.ws_urls = urls
        self.state.role = self.role_var.get()
        for url in urls:
            self.ws_manager.connect(url)
            self.ws_manager.send(url, {"task": "heartbeat", "role": self.state.role})
        if urls:
            self.state.active_ws = urls[0]
        self.state.log(f"Connecting to {len(urls)} endpoint(s) as {self.state.role}")
        self._refresh_logs()

    def _heartbeat_all(self):
        for url in self.state.ws_urls:
            self.ws_manager.send(url, {"task": "heartbeat", "role": self.role_var.get()})
        self.state.log("Heartbeat requested for all connected servers.")
        self._refresh_logs()

    def _on_select_server(self, _event=None):
        selection = self.server_tree.selection()
        if not selection:
            return
        self.state.active_ws = selection[0]
        self._render_selected()

    def _request_metrics(self):
        srv = self.state.active_server()
        if not srv:
            return
        self.ws_manager.send(srv.ws_url, {"task": "metrics", "role": self.role_var.get()})
        self.state.log(f"Requested metrics from {srv.ws_url}")
        self._refresh_logs()

    def _push_settings(self):
        srv = self.state.active_server()
        if not srv:
            return
        srv.status = self.status_var.get()
        srv.ws_url = self.ws_var.get()
        payload = {
            "task": "admin_control",
            "action": "update_settings",
            "role": self.role_var.get(),
            "settings": {
                "status": srv.status,
                "ws_url": srv.ws_url,
            },
        }
        self.ws_manager.send(srv.ws_url, payload)
        self.state.log(f"Pushed settings to {srv.ws_url}")
        self._refresh_server_list()

    def _push_storage(self):
        srv = self.state.active_server()
        if not srv:
            return
        srv.settings.docker_image = self.docker_var.get()
        srv.settings.mergerfs_source = self.merger_src_var.get()
        srv.settings.mergerfs_target = self.merger_tgt_var.get()
        srv.settings.samba_share = self.samba_share_var.get()
        srv.settings.samba_user = self.samba_user_var.get()
        srv.settings.samba_pass = self.samba_pass_var.get()
        payload = {
            "task": "docker_run",
            "role": self.role_var.get(),
            "image": srv.settings.docker_image,
            "volumes": [
                f"{srv.settings.mergerfs_source}:{srv.settings.mergerfs_target}",
                f"{srv.settings.samba_share}:/samba/share",
            ],
            "env": {
                "SAMBA_USER": srv.settings.samba_user,
                "SAMBA_PASS": srv.settings.samba_pass,
            },
        }
        targets = self.state.ws_urls if self.storage_all_var.get() else [srv.ws_url]
        for url in targets:
            self.ws_manager.send(url, payload)
        target_label = "all servers" if self.storage_all_var.get() else srv.ws_url
        self.state.log(f"Sent storage/Docker config to {target_label}")
        self._refresh_logs()

    def _run_command(self):
        srv = self.state.active_server()
        cmd = self.cmd_var.get().strip()
        if not srv or not cmd:
            return
        self.ws_manager.send(srv.ws_url, {"task": "cmd", "role": self.role_var.get(), "command": cmd})
        self.state.log(f"Command '{cmd}' sent to {srv.ws_url}")
        self.cmd_var.set("")
        self._refresh_logs()

    def _request_tasks(self):
        srv = self.state.active_server()
        if not srv:
            return
        self.ws_manager.send(srv.ws_url, {"task": "tasks", "role": self.role_var.get()})
        self.state.log(f"Requested tasks from {srv.ws_url}")
        self._refresh_logs()

    def _task_action(self, action: str):
        srv = self.state.active_server()
        selection = self.task_list.curselection()
        if not srv or not selection:
            return
        task = srv.tasks[selection[0]]
        if action == "stop":
            payload = {"task": "stop", "role": self.role_var.get(), "pid": int(task.name)}
            self.ws_manager.send(srv.ws_url, payload)
            self.state.log(f"Sent stop for pid {task.name} on {srv.ws_url}")
        self._refresh_logs()

    def _apply_lb(self):
        self.state.lb_mode = self.lb_mode_var.get()
        self.state.log(f"LB mode set to {self.state.lb_mode}")
        self._refresh_logs()

    def _save_targets(self):
        targets = [t.strip() for t in self.lb_targets_var.get().split(",") if t.strip()]
        self.state.lb_targets = targets
        self.state.log(f"LB targets set: {targets}")
        self._refresh_logs()

    # ---------- Rendering ----------
    def _refresh_server_list(self):
        self.server_tree.delete(*self.server_tree.get_children())
        for url, srv in self.state.servers.items():
            node_label = srv.node_id or url
            self.server_tree.insert("", "end", iid=url, values=(node_label, srv.role, srv.status))

    def _render_selected(self):
        srv = self.state.active_server()
        if not srv:
            self.selected_label.config(text="No server selected")
            self.meta_label.config(text="")
            return
        self.selected_label.config(text=f"{srv.node_id or srv.ws_url} ({srv.role})")
        meta = f"{srv.private_ip or 'n/a'} | {srv.ws_url} | status: {srv.status}"
        self.meta_label.config(text=meta)
        self.status_var.set(srv.status)
        self.ws_var.set(srv.ws_url)

        self.docker_var.set(srv.settings.docker_image)
        self.merger_src_var.set(srv.settings.mergerfs_source)
        self.merger_tgt_var.set(srv.settings.mergerfs_target)
        self.samba_share_var.set(srv.settings.samba_share)
        self.samba_user_var.set(srv.settings.samba_user)
        self.samba_pass_var.set(srv.settings.samba_pass)

        self._render_tasks()
        self._render_metrics(srv)

    def _render_tasks(self):
        self.task_list.delete(0, tk.END)
        srv = self.state.active_server()
        if not srv:
            return
        for t in srv.tasks:
            self.task_list.insert(tk.END, f"{t.name} [{t.status}]")

    def _render_metrics(self, srv: Server):
        self.canvas.delete("all")
        width = self.canvas.winfo_width() or 640
        height = self.canvas.winfo_height() or 180
        bars = [("CPU", srv.cpu, "#3a86ff"), ("Mem", srv.mem, "#4cc9f0"), ("Net", srv.net, "#00f5d4")]
        for idx, (label, val, color) in enumerate(bars):
            x0 = 30 + idx * (width // 3)
            y0 = height - 30
            bar_h = int(val * (height - 60))
            self.canvas.create_rectangle(x0, y0 - bar_h, x0 + 140, y0, fill=color, width=0)
            self.canvas.create_text(x0 + 70, y0 - bar_h - 12, text=f"{label} {int(val*100)}%", fill="#e2ecff", font=("Segoe UI", 10, "bold"))
        # waveform aesthetic
        points = []
        for i in range(80):
            x = 10 + i * (width - 20) / 80
            y = height / 2 + math.sin(i / 4) * 16
            points.extend([x, y])
        self.canvas.create_line(points, fill="#7ee0ff", smooth=True, width=2)
        self.overview_text.config(text="Metrics sourced from live WS 'metrics' responses. Heartbeat populates identity.")

    def _refresh_logs(self):
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(tk.END, "\n".join(self.state.logs))

    def _refresh_logs_loop(self):
        self._refresh_logs()
        self.after(1200, self._refresh_logs_loop)


def run():
    state = AppState()
    app = AdminApp(state)
    app.mainloop()


if __name__ == "__main__":
    run()

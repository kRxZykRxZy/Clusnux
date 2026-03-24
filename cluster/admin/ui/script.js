(() => {
  const state = {
    ws: null,
    role: "admin",
    connected: false,
  };

  const roleSelect = document.getElementById("role");
  const wsInput = document.getElementById("ws-url");
  const connectBtn = document.getElementById("connect-btn");
  const statusEl = document.getElementById("status");
  const heartbeatBtn = document.getElementById("heartbeat-btn");
  const heartbeatOutput = document.getElementById("heartbeat-output");
  const heartbeatState = document.getElementById("heartbeat-state");
  const cmdInput = document.getElementById("cmd-input");
  const cmdOutput = document.getElementById("cmd-output");
  const runBtn = document.getElementById("run-btn");
  const clearOutputBtn = document.getElementById("clear-output-btn");
  const rolePill = document.getElementById("role-pill");

  roleSelect.addEventListener("change", () => {
    state.role = roleSelect.value;
    rolePill.textContent = state.role;
    log(`Role switched to ${state.role}`);
  });

  connectBtn.addEventListener("click", () => {
    const url = wsInput.value.trim();
    if (!url) {
      statusEl.textContent = "Missing WebSocket URL";
      return;
    }
    connect(url);
  });

  heartbeatBtn.addEventListener("click", () => {
    send({ task: "heartbeat", role: state.role });
    heartbeatState.textContent = "sent";
  });

  runBtn.addEventListener("click", () => {
    const command = cmdInput.value.trim();
    if (!command) return;
    send({ task: "cmd", command, role: state.role });
  });

  clearOutputBtn.addEventListener("click", () => {
    cmdOutput.textContent = "";
    heartbeatOutput.textContent = "";
  });

  function connect(url) {
    if (state.ws) {
      state.ws.close();
    }

    statusEl.textContent = "Connecting…";
    state.ws = new WebSocket(url);

    state.ws.onopen = () => {
      state.connected = true;
      statusEl.textContent = `Connected as ${state.role}`;
      log(`Connected to ${url}`);
    };

    state.ws.onclose = () => {
      state.connected = false;
      statusEl.textContent = "Disconnected";
      log("Connection closed");
    };

    state.ws.onerror = (err) => {
      statusEl.textContent = "Connection error";
      console.error(err);
    };

    state.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (e) {
        log(event.data);
      }
    };
  }

  function send(payload) {
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
      statusEl.textContent = "Not connected";
      return;
    }
    state.ws.send(JSON.stringify(payload));
  }

  function handleMessage(data) {
    if (data.task === "heartbeat") {
      heartbeatState.textContent = "ok";
      heartbeatOutput.textContent = JSON.stringify(data, null, 2);
    } else if (data.task?.startsWith("cmd")) {
      log(`[${data.task}] ${JSON.stringify(data)}`);
    } else if (data.status === "error") {
      log(`Error: ${data.code || data.status}`);
    } else {
      log(JSON.stringify(data));
    }
  }

  function log(line) {
    cmdOutput.textContent += `${line}\n`;
    cmdOutput.scrollTop = cmdOutput.scrollHeight;
  }
})();

const LAUNCHER_BASE = "http://127.0.0.1:17890";
const LAUNCHER_CMD = 'python "H:\\Projects\\HR Agent\\scripts\\launcher.py"';

window.HrAgentBackend = {
  async launcherRequest(path, options = {}) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        {
          type: "LAUNCHER",
          path,
          method: options.method || "GET",
          body: options.body || null,
        },
        (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
            return;
          }
          if (!response?.ok) {
            reject(new Error(response?.error || `Launcher error ${response?.status}`));
            return;
          }
          resolve(response.data);
        }
      );
    });
  },

  async getStatus() {
    try {
      const health = await HrAgentApi.health();
      const versionOk = !health.version || health.version === "0.3.0";
      return { backend: versionOk, launcher: true };
    } catch (_error) {
      try {
        const launcherStatus = await this.launcherRequest("/backend-status");
        return {
          backend: Boolean(launcherStatus.backend_running),
          launcher: true,
        };
      } catch (_launcherError) {
        return { backend: false, launcher: false };
      }
    }
  },

  async startBackend() {
    const status = await this.getStatus();
    if (status.backend) {
      return { status: "already_running" };
    }

    if (!status.launcher) {
      await navigator.clipboard.writeText(LAUNCHER_CMD);
      throw new Error(
        "Launcher is offline. Command copied to clipboard. Run it once, then press Start backend again."
      );
    }

    const result = await this.launcherRequest("/start-backend", { method: "POST" });
    for (let attempt = 0; attempt < 15; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      try {
        await HrAgentApi.health();
        return result;
      } catch (_error) {
        // keep waiting
      }
    }
    throw new Error("Backend start requested, but health check timed out.");
  },

  async stopBackend() {
    const status = await this.getStatus();
    if (!status.backend && !status.launcher) {
      throw new Error("Backend is already offline.");
    }

    if (!status.launcher) {
      throw new Error("Launcher is offline. Cannot stop backend from extension.");
    }

    const result = await this.launcherRequest("/stop-backend", { method: "POST" });
    for (let attempt = 0; attempt < 8; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      const nextStatus = await this.getStatus();
      if (!nextStatus.backend) {
        return result;
      }
    }

    if (result?.status === "still_running") {
      throw new Error("Stop requested, but backend still responds.");
    }
    return result;
  },

  renderStatus(status) {
    const online = Boolean(status.backend);
    const launcherOk = Boolean(status.launcher);
    HrAgentPanel.setBackendOnline(online);

    if (online) {
      HrAgentPanel.setBackendStatus("", false);
    } else {
      HrAgentPanel.setBackendStatus(
        launcherOk
          ? "Backend offline · open ⋯ More → Start backend"
          : "Run scripts/launcher.py once, then Start backend",
        true
      );
    }

    const startButton = HrAgentPanel.ensure().querySelector("#hr-agent-start-backend");
    const stopButton = HrAgentPanel.ensure().querySelector("#hr-agent-stop-backend");
    if (startButton) {
      startButton.classList.toggle("hr-agent-hidden", Boolean(status.backend));
    }
    if (stopButton) {
      stopButton.classList.toggle("hr-agent-hidden", !status.backend || !status.launcher);
    }
  },

  async refreshStatus() {
    const status = await this.getStatus();
    this.renderStatus(status);
    return status;
  },
};

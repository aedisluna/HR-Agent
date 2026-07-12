const EXPECTED_API_MAJOR_MINOR = "0.6";

function apiVersionCompatible(version) {
  if (!version) return true;
  return String(version).split(".").slice(0, 2).join(".") === EXPECTED_API_MAJOR_MINOR;
}

window.HrAgentBackend = {
  async nativeHostRequest(action) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: "NATIVE_HOST", action }, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        if (!response?.ok) {
          reject(new Error(response?.error || "Local launcher bridge is unavailable."));
          return;
        }
        resolve(response.data);
      });
    });
  },

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
    let backend = false;
    try {
      const health = await HrAgentApi.health();
      backend = apiVersionCompatible(health.version);
    } catch (_error) {
      // The launcher check below determines whether a stopped backend can start.
    }

    try {
      const launcherStatus = await this.launcherRequest("/backend-status");
      return {
        backend: backend || Boolean(launcherStatus.backend_running),
        launcher: true,
      };
    } catch (_launcherError) {
      return { backend, launcher: false };
    }
  },

  async ensureLauncher() {
    try {
      await this.launcherRequest("/health");
      return;
    } catch (_error) {
      // The native host starts the launcher in a detached local process.
    }

    await this.nativeHostRequest("ensure_launcher");
    for (let attempt = 0; attempt < 8; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      try {
        await this.launcherRequest("/health");
        return;
      } catch (_error) {
        // wait for the launcher to bind its local port
      }
    }
    throw new Error("Local launcher did not become ready.");
  },

  async startBackend() {
    const status = await this.getStatus();
    if (status.backend) {
      return { status: "already_running" };
    }

    if (!status.launcher) {
      await this.ensureLauncher();
    }

    const result = await this.launcherRequest("/start-backend", { method: "POST" });
    if (result?.status === "runtime_error" || result?.error) {
      throw new Error(result.error || "Backend runtime is not ready.");
    }
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
      await this.ensureLauncher();
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
          : "Install the local bridge once, then press Start backend",
        true
      );
    }

    const startButton = HrAgentPanel.ensure().querySelector("#hr-agent-start-backend");
    const stopButton = HrAgentPanel.ensure().querySelector("#hr-agent-stop-backend");
    if (startButton) {
      startButton.classList.toggle("hr-agent-hidden", Boolean(status.backend));
    }
    if (stopButton) {
      stopButton.classList.toggle("hr-agent-hidden", !status.backend);
    }
  },

  async refreshStatus() {
    const status = await this.getStatus();
    this.renderStatus(status);
    return status;
  },
};

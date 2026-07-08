const API_BASE = "http://127.0.0.1:8001";

window.HrAgentApi = {
  APPLICATIONS_UI_URL: `${API_BASE}/applications/ui`,
  async request(path, { method = "GET", body = null } = {}) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { type: "API", path, method, body },
        (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
            return;
          }
          if (!response?.ok) {
            reject(
              new Error(
                response?.data?.detail ||
                  response?.error ||
                  `API error ${response?.status || "unknown"}`
              )
            );
            return;
          }
          resolve(response.data);
        }
      );
    });
  },

  health() {
    return this.request("/health");
  },

  analyzePage(payload) {
    return this.request("/extension/analyze-page", {
      method: "POST",
      body: payload,
    });
  },

  fillForm(payload) {
    return this.request("/extension/fill-form", {
      method: "POST",
      body: payload,
    });
  },

  generateCv(payload) {
    return this.request("/extension/generate-cv", {
      method: "POST",
      body: payload,
    });
  },

  saveAnswer(payload) {
    return this.request("/extension/save-answer", {
      method: "POST",
      body: payload,
    });
  },

  getLogs(source = "all", lines = 200) {
    return this.request(`/debug/logs?source=${source}&lines=${lines}`);
  },

  clearLogs(source = "all") {
    return this.request(`/debug/logs?source=${source}`, { method: "DELETE" });
  },

  getApplicationByUrl(url) {
    return this.request(`/extension/application-by-url?url=${encodeURIComponent(url)}`);
  },

  updateApplication(id, payload) {
    return this.request(`/applications/${id}`, {
      method: "PATCH",
      body: payload,
    });
  },

  listApplications(limit = 20) {
    return this.request(`/extension/applications?limit=${limit}`);
  },

  trackApplication(payload) {
    return this.request("/extension/track-application", {
      method: "POST",
      body: payload,
    });
  },

  saveJobContext(context) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { type: "SAVE_JOB_CONTEXT", context },
        () => resolve()
      );
    });
  },

  getJobContext() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "GET_JOB_CONTEXT" }, (response) => {
        resolve(response?.context || null);
      });
    });
  },
};

const API_BASE = "http://127.0.0.1:8001";
const LAUNCHER_BASE = "http://127.0.0.1:17890";
const LAUNCHER_CLIENT_HEADER = "X-HR-Agent-Client";
const NATIVE_HOST_NAME = "com.hr_agent.launcher";
const EXTENSION_LOG_KEY = "hrAgentExtensionLogs";
const MAX_EXTENSION_LOGS = 200;
let extensionLogChain = Promise.resolve();

function safeApiPath(path) {
  if (typeof path !== "string" || !path.startsWith("/") || path.startsWith("//")) {
    throw new Error("Invalid API path");
  }
  if (path.includes("://")) {
    throw new Error("Invalid API path");
  }
  return path;
}

function withExtensionLogs(updateFn) {
  extensionLogChain = extensionLogChain.then(
    () =>
      new Promise((resolve) => {
        chrome.storage.local.get(EXTENSION_LOG_KEY, (result) => {
          const entries = result[EXTENSION_LOG_KEY] || [];
          const nextEntries = updateFn(entries);
          chrome.storage.local.set(
            { [EXTENSION_LOG_KEY]: nextEntries.slice(-MAX_EXTENSION_LOGS) },
            resolve
          );
        });
      })
  );
  return extensionLogChain;
}

function appendExtensionLog(entry) {
  void withExtensionLogs((entries) => {
    entries.push(entry);
    return entries;
  });
}

function summarizeBody(body) {
  if (!body || typeof body !== "object") return null;
  const summary = {};
  if (body.platform) summary.platform = body.platform;
  if (body.url) summary.url = body.url;
  if (Array.isArray(body.fields)) summary.fields = body.fields.length;
  if (body.question_pattern) summary.question = String(body.question_pattern).slice(0, 80);
  if (body.job_text) summary.job_chars = String(body.job_text).length;
  return Object.keys(summary).length ? summary : null;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "NATIVE_HOST") {
    chrome.runtime.sendNativeMessage(
      NATIVE_HOST_NAME,
      { action: message.action || "" },
      (response) => {
        if (chrome.runtime.lastError) {
          const error = chrome.runtime.lastError.message;
          appendExtensionLog({
            ts: new Date().toISOString().replace("T", " ").slice(0, 19),
            level: "ERROR",
            message: "Native launcher bridge failed",
            meta: { error },
          });
          sendResponse({ ok: false, error });
          return;
        }
        if (!response?.ok) {
          sendResponse({ ok: false, error: response?.error || "Native launcher bridge failed." });
          return;
        }
        appendExtensionLog({
          ts: new Date().toISOString().replace("T", " ").slice(0, 19),
          level: "INFO",
          message: "Native launcher bridge ready",
          meta: response,
        });
        sendResponse({ ok: true, data: response });
      }
    );
    return true;
  }

  if (message.type === "API") {
    const method = message.method || "GET";
    let apiPath;
    try {
      apiPath = safeApiPath(message.path);
    } catch (error) {
      sendResponse({ ok: false, error: String(error) });
      return true;
    }
    const isLogMaintenance =
      apiPath.startsWith("/debug/logs") &&
      (method === "GET" || method === "DELETE");

    if (!isLogMaintenance) {
      appendExtensionLog({
        ts: new Date().toISOString().replace("T", " ").slice(0, 19),
        level: "INFO",
        message: `API ${method} ${apiPath}`,
        meta: summarizeBody(message.body),
      });
    }

    fetch(`${API_BASE}${apiPath}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: message.body ? JSON.stringify(message.body) : undefined,
    })
      .then(async (response) => {
        const raw = await response.text();
        let data = {};
        if (raw) {
          try {
            data = JSON.parse(raw);
          } catch (_error) {
            data = { detail: raw.slice(0, 300) };
          }
        }
        if (!isLogMaintenance) {
          appendExtensionLog({
            ts: new Date().toISOString().replace("T", " ").slice(0, 19),
            level: response.ok ? "INFO" : "ERROR",
            message: `API ${method} ${apiPath} -> ${response.status}`,
            meta: response.ok
              ? null
              : { detail: data.detail || data.error || "request failed" },
          });
        }
        sendResponse({
          ok: response.ok,
          status: response.status,
          data,
        });
      })
      .catch((error) => {
        if (!isLogMaintenance) {
          appendExtensionLog({
            ts: new Date().toISOString().replace("T", " ").slice(0, 19),
            level: "ERROR",
            message: `API ${method} ${apiPath} failed`,
            meta: { error: String(error) },
          });
        }
        sendResponse({ ok: false, error: String(error) });
      });
    return true;
  }

  if (message.type === "LAUNCHER") {
    const method = message.method || "GET";
    let launcherPath;
    try {
      launcherPath = safeApiPath(message.path);
    } catch (error) {
      sendResponse({ ok: false, error: String(error) });
      return true;
    }
    appendExtensionLog({
      ts: new Date().toISOString().replace("T", " ").slice(0, 19),
      level: "INFO",
      message: `Launcher ${method} ${launcherPath}`,
      meta: null,
    });

    fetch(`${LAUNCHER_BASE}${launcherPath}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        [LAUNCHER_CLIENT_HEADER]: "extension",
      },
      body: message.body ? JSON.stringify(message.body) : undefined,
    })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        appendExtensionLog({
          ts: new Date().toISOString().replace("T", " ").slice(0, 19),
          level: response.ok ? "INFO" : "ERROR",
          message: `Launcher ${method} ${launcherPath} -> ${response.status}`,
          meta: response.ok ? data : { error: data.error || "request failed" },
        });
        sendResponse({
          ok: response.ok,
          status: response.status,
          data,
        });
      })
      .catch((error) => {
        appendExtensionLog({
          ts: new Date().toISOString().replace("T", " ").slice(0, 19),
          level: "ERROR",
          message: `Launcher ${method} ${launcherPath} failed`,
          meta: { error: String(error) },
        });
        sendResponse({ ok: false, error: String(error) });
      });
    return true;
  }

  if (message.type === "SAVE_EXTENSION_LOGS") {
    void withExtensionLogs(() => (message.entries || []).slice(-MAX_EXTENSION_LOGS)).then(
      () => sendResponse({ ok: true })
    );
    return true;
  }

  if (message.type === "CLEAR_EXTENSION_LOGS") {
    void withExtensionLogs(() => []).then(() => sendResponse({ ok: true }));
    return true;
  }

  if (message.type === "GET_EXTENSION_LOGS") {
    chrome.storage.local.get(EXTENSION_LOG_KEY, (result) => {
      sendResponse({ entries: result[EXTENSION_LOG_KEY] || [] });
    });
    return true;
  }

  if (message.type === "SAVE_JOB_CONTEXT") {
    chrome.storage.session.set({ jobContext: message.context }, () => {
      sendResponse({ ok: true });
    });
    return true;
  }

  if (message.type === "GET_JOB_CONTEXT") {
    chrome.storage.session.get("jobContext", (result) => {
      sendResponse({ context: result.jobContext || null });
    });
    return true;
  }

  if (message.type === "CLEAR_JOB_CONTEXT") {
    chrome.storage.session.remove("jobContext", () => {
      sendResponse({ ok: true });
    });
    return true;
  }

  if (message.type === "HR_AGENT_BROADCAST") {
    const tabId = _sender.tab?.id;
    if (!tabId) {
      sendResponse([]);
      return true;
    }

    chrome.webNavigation.getAllFrames({ tabId }, (frames) => {
      if (!frames?.length) {
        sendResponse([]);
        return;
      }

      Promise.all(
        frames.map((frame) =>
          chrome.tabs
            .sendMessage(
              tabId,
              { type: message.innerType, ...(message.payload || {}) },
              { frameId: frame.frameId }
            )
            .catch(() => null)
        )
      ).then((results) => sendResponse(results.filter(Boolean)));
    });
    return true;
  }

  return false;
});

chrome.action.onClicked.addListener((tab) => {
  if (!tab.id) return;
  chrome.tabs.sendMessage(tab.id, { type: "TOGGLE_PANEL" });
});

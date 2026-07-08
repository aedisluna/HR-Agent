window.HrAgentPanel = {
  root: null,
  _moreOpen: false,

  ensure() {
    if (this.root) return this.root;

    const root = document.createElement("div");
    root.id = "hr-agent-panel";
    root.innerHTML = `
      <div class="hr-agent-header">
        <div class="hr-agent-brand">
          <span class="hr-agent-status-dot offline" id="hr-agent-status-dot" title="Backend status"></span>
          <strong>HR Agent</strong>
        </div>
        <div class="hr-agent-header-actions">
          <button type="button" id="hr-agent-close" title="Close">×</button>
        </div>
      </div>
      <div class="hr-agent-backend-line hidden" id="hr-agent-backend-status">Checking backend…</div>
      <div class="hr-agent-body">
        <div class="hr-agent-scroll">
          <div class="hr-agent-job-card">
            <div class="hr-agent-job-title-row">
              <div class="hr-agent-job-title-block">
                <div class="hr-agent-company" id="hr-agent-company">Open a vacancy page</div>
                <div class="hr-agent-role" id="hr-agent-role">to begin</div>
                <div class="hr-agent-platform" id="hr-agent-platform"></div>
              </div>
              <div class="hr-agent-fit-badge hidden" id="hr-agent-fit-badge" title="Fit score">—</div>
            </div>
            <div class="hr-agent-salary hidden" id="hr-agent-salary"></div>
            <div class="hr-agent-keywords hidden" id="hr-agent-keywords"></div>
            <div class="hr-agent-track-row">
              <label class="sr-only" for="hr-agent-job-status">Application status</label>
              <select id="hr-agent-job-status" class="hr-agent-status-select">
                <option value="draft">Saved</option>
                <option value="applied">Applied</option>
                <option value="waiting">Waiting</option>
                <option value="recruiter_screen">Screen</option>
                <option value="test_task">Test task</option>
                <option value="interview">Interview</option>
                <option value="rejected">Rejected</option>
                <option value="offer">Offer</option>
              </select>
              <button type="button" id="hr-agent-open-applications" class="btn-icon" title="Open stats">📊</button>
            </div>
            <textarea id="hr-agent-job-notes" class="hr-agent-notes" rows="2" placeholder="Notes about this vacancy…" spellcheck="false"></textarea>
            <div class="hr-agent-lang-row">
              <label for="hr-agent-language">Language</label>
              <select id="hr-agent-language">
                <option value="auto">Auto</option>
                <option value="ru">Русский</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>

          <div class="hr-agent-section">
            <div class="hr-agent-actions-primary">
              <button type="button" id="hr-agent-analyze" class="btn-primary">Analyze</button>
              <button type="button" id="hr-agent-generate-cv" class="btn-primary">CV</button>
              <button type="button" id="hr-agent-fill" class="btn-primary">Fill</button>
            </div>
            <div class="hr-agent-more-wrap">
              <button type="button" id="hr-agent-more-toggle" class="btn-secondary hr-agent-more-btn">⋯ More</button>
              <div class="hr-agent-more-menu hidden" id="hr-agent-more-menu">
                <button type="button" id="hr-agent-track-vacancy">Save vacancy</button>
                <button type="button" id="hr-agent-mark-applied">Mark applied</button>
                <button type="button" id="hr-agent-copy">Copy output</button>
                <button type="button" id="hr-agent-save-context">Save context</button>
                <button type="button" id="hr-agent-logs">Debug logs</button>
                <button type="button" id="hr-agent-start-backend">Start backend</button>
                <button type="button" id="hr-agent-stop-backend">Stop backend</button>
              </div>
            </div>
          </div>

          <div class="hr-agent-collapsible" id="hr-agent-questions-section">
            <button type="button" class="hr-agent-collapsible-toggle" id="hr-agent-questions-toggle">
              <span>Questions for you <span class="hr-agent-badge hidden" id="hr-agent-questions-badge">0</span></span>
              <span class="chevron">›</span>
            </button>
            <div class="hr-agent-collapsible-body">
              <div class="hr-agent-questions" id="hr-agent-questions">
                <div class="hr-agent-question-empty">No pending questions.</div>
              </div>
            </div>
          </div>

          <div class="hr-agent-collapsible hidden" id="hr-agent-logs-section">
            <button type="button" class="hr-agent-collapsible-toggle" id="hr-agent-logs-toggle">
              <span>Debug logs</span>
              <span class="chevron">›</span>
            </button>
            <div class="hr-agent-collapsible-body">
              <div class="hr-agent-logs-panel" id="hr-agent-logs-panel">
                <div class="hr-agent-logs-toolbar">
                  <button type="button" id="hr-agent-logs-refresh" class="btn-secondary">Refresh</button>
                  <button type="button" id="hr-agent-logs-copy" class="btn-secondary">Copy</button>
                  <button type="button" id="hr-agent-logs-clear" class="btn-ghost" title="Clear all logs">Clear</button>
                </div>
                <pre class="hr-agent-logs-output" id="hr-agent-logs-output"></pre>
              </div>
            </div>
          </div>
        </div>

        <div class="hr-agent-output-wrap hidden" id="hr-agent-output-wrap">
          <div class="hr-agent-output-header">
            <span>Output</span>
            <button type="button" id="hr-agent-output-clear" class="btn-ghost">Clear</button>
          </div>
          <textarea class="hr-agent-output" id="hr-agent-output" readonly spellcheck="false" aria-label="Output"></textarea>
        </div>
      </div>

      <div class="hr-agent-footer">
        <div class="hr-agent-status" id="hr-agent-status">Ready</div>
      </div>
      <div class="hr-agent-resize-grip" title="Drag to resize" aria-hidden="true"></div>
    `;
    document.documentElement.appendChild(root);

    root.querySelector("#hr-agent-close").addEventListener("click", () => {
      root.classList.add("hidden");
    });

    root.querySelector("#hr-agent-questions-toggle").addEventListener("click", () => {
      this.toggleCollapsible("hr-agent-questions-section");
    });

    root.querySelector("#hr-agent-logs-toggle").addEventListener("click", () => {
      this.toggleCollapsible("hr-agent-logs-section");
    });

    root.querySelector("#hr-agent-output-clear").addEventListener("click", () => {
      this.setOutput("");
    });

    root.querySelector("#hr-agent-more-toggle").addEventListener("click", (event) => {
      event.stopPropagation();
      this.toggleMoreMenu();
    });

    const moreMenu = root.querySelector("#hr-agent-more-menu");
    moreMenu.addEventListener("click", (event) => {
      event.stopPropagation();
      if (event.target.closest("button")) {
        this.toggleMoreMenu(false);
      }
    });

    document.addEventListener("click", (event) => {
      if (!this._moreOpen || !this.root) return;
      const wrap = this.root.querySelector(".hr-agent-more-wrap");
      if (wrap?.contains(event.target)) return;
      this.toggleMoreMenu(false);
    });

    this._loadPanelSize(root);
    this._watchPanelSize(root);
    this._initPanelResize(root);

    const output = root.querySelector("#hr-agent-output");
    if (output) {
      output.addEventListener("mousedown", (event) => event.stopPropagation());
      output.addEventListener("pointerdown", (event) => event.stopPropagation());
    }

    root.classList.add("hidden");
    this.root = root;
    return root;
  },

  toggleMoreMenu(forceOpen = null) {
    const menu = this.ensure().querySelector("#hr-agent-more-menu");
    const shouldOpen = forceOpen === null ? menu.classList.contains("hidden") : forceOpen;
    menu.classList.toggle("hidden", !shouldOpen);
    menu.classList.toggle("open", shouldOpen);
    this._moreOpen = shouldOpen;
  },

  _loadPanelSize(root) {
    try {
      chrome.storage.local.get("hrAgentPanelSize", (result) => {
        const size = result?.hrAgentPanelSize;
        if (!size) return;
        if (size.width) root.style.width = `${size.width}px`;
        if (size.height) root.style.height = `${size.height}px`;
      });
    } catch (_error) {
      // storage unavailable
    }
  },

  _watchPanelSize(root) {
    if (typeof ResizeObserver === "undefined") return;
    let saveTimer = null;
    const observer = new ResizeObserver(() => {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => {
        try {
          chrome.storage.local.set({
            hrAgentPanelSize: {
              width: root.offsetWidth,
              height: root.offsetHeight,
            },
          });
        } catch (_error) {
          // storage unavailable
        }
      }, 200);
    });
    observer.observe(root);
  },

  _initPanelResize(root) {
    const grip = root.querySelector(".hr-agent-resize-grip");
    if (!grip) return;

    const minWidth = 300;
    const minHeight = 420;

    grip.addEventListener("mousedown", (event) => {
      event.preventDefault();
      event.stopPropagation();

      const startX = event.clientX;
      const startY = event.clientY;
      const startWidth = root.offsetWidth;
      const startHeight = root.offsetHeight;
      const maxHeight = window.innerHeight - 24;

      const onMove = (moveEvent) => {
        const width = Math.max(minWidth, startWidth + (startX - moveEvent.clientX));
        const height = Math.max(
          minHeight,
          Math.min(maxHeight, startHeight + (moveEvent.clientY - startY))
        );
        root.style.width = `${width}px`;
        root.style.height = `${height}px`;
      };

      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  },

  toggleCollapsible(sectionId, forceOpen = null) {
    const section = this.ensure().querySelector(`#${sectionId}`);
    if (!section) return false;
    const shouldOpen =
      forceOpen === null ? !section.classList.contains("open") : forceOpen;
    section.classList.toggle("open", shouldOpen);
    return shouldOpen;
  },

  setQuestionsCount(count) {
    const badge = this.ensure().querySelector("#hr-agent-questions-badge");
    if (!badge) return;
    badge.textContent = String(count);
    badge.classList.toggle("hidden", !count);
  },

  open() {
    const root = this.ensure();
    root.classList.remove("hidden");
    return root;
  },

  hide() {
    if (this.root) {
      this.root.classList.add("hidden");
    }
  },

  toggle() {
    const root = this.ensure();
    root.classList.toggle("hidden");
  },

  getLanguage() {
    return this.ensure().querySelector("#hr-agent-language").value || "auto";
  },

  setMeta(text) {
    this.setJobTitle(text, "", "");
  },

  setJobTitle(company, role, platform = "") {
    this.ensure().querySelector("#hr-agent-company").textContent = company || "Company";
    this.ensure().querySelector("#hr-agent-role").textContent = role || "Role";
    const platformEl = this.ensure().querySelector("#hr-agent-platform");
    platformEl.textContent = platform || "";
    platformEl.classList.toggle("hidden", !platform);
  },

  setFitScore(score) {
    const badge = this.ensure().querySelector("#hr-agent-fit-badge");
    if (score == null || score === "" || Number.isNaN(Number(score))) {
      badge.classList.add("hidden");
      return;
    }
    const value = Number(score);
    badge.textContent = String(value);
    badge.classList.remove("hidden", "fit-high", "fit-mid", "fit-low");
    if (value >= 75) badge.classList.add("fit-high");
    else if (value >= 50) badge.classList.add("fit-mid");
    else badge.classList.add("fit-low");
  },

  setSalary(text) {
    const el = this.ensure().querySelector("#hr-agent-salary");
    if (!text) {
      el.classList.add("hidden");
      el.textContent = "";
      return;
    }
    el.textContent = text;
    el.classList.remove("hidden");
  },

  setKeywords(keywords) {
    const el = this.ensure().querySelector("#hr-agent-keywords");
    const items = (keywords || []).filter(Boolean);
    if (!items.length) {
      el.classList.add("hidden");
      el.innerHTML = "";
      return;
    }
    el.innerHTML = items
      .map((keyword) => `<span class="hr-agent-keyword">${HrAgentExtractors.escapeHtml(keyword)}</span>`)
      .join("");
    el.classList.remove("hidden");
  },

  setJobStatus(status) {
    const select = this.ensure().querySelector("#hr-agent-job-status");
    if (select && status) select.value = status;
  },

  getJobStatus() {
    return this.ensure().querySelector("#hr-agent-job-status")?.value || "draft";
  },

  setNotes(text, options = {}) {
    const textarea = this.ensure().querySelector("#hr-agent-job-notes");
    if (!textarea) return;
    if (!options.silent) {
      textarea.value = text || "";
      return;
    }
    if (document.activeElement !== textarea) {
      textarea.value = text || "";
    }
  },

  getNotes() {
    return this.ensure().querySelector("#hr-agent-job-notes")?.value?.trim() || "";
  },

  setBackendStatus(text, visible = true) {
    const line = this.ensure().querySelector("#hr-agent-backend-status");
    line.textContent = text;
    line.classList.toggle("hidden", !visible);
  },

  setBackendOnline(online) {
    const dot = this.ensure().querySelector("#hr-agent-status-dot");
    if (dot) {
      dot.classList.toggle("online", Boolean(online));
      dot.classList.toggle("offline", !online);
      dot.title = online ? "Backend online" : "Backend offline";
    }
  },

  setStatus(text, tone = "default") {
    const el = this.ensure().querySelector("#hr-agent-status");
    el.textContent = text;
    el.classList.remove("busy", "error", "success");
    if (tone === "busy") el.classList.add("busy");
    if (tone === "error") el.classList.add("error");
    if (tone === "success") el.classList.add("success");
  },

  setOutput(text) {
    const wrap = this.ensure().querySelector("#hr-agent-output-wrap");
    const output = this.ensure().querySelector("#hr-agent-output");
    output.value = text;
    this._lastOutput = text;
    wrap.classList.toggle("hidden", !text);
  },

  getOutput() {
    return (
      this._lastOutput ||
      this.ensure().querySelector("#hr-agent-output")?.value ||
      ""
    );
  },

  toggleLogsPanel(forceOpen = null) {
    const section = this.ensure().querySelector("#hr-agent-logs-section");
    section.classList.remove("hidden");
    const shouldOpen = this.toggleCollapsible("hr-agent-logs-section", forceOpen);
    return shouldOpen;
  },

  setLogs(text) {
    const output = this.ensure().querySelector("#hr-agent-logs-output");
    if (output) output.textContent = text;
    this._lastLogs = text;
  },

  getLogs() {
    return (
      this._lastLogs ||
      this.ensure().querySelector("#hr-agent-logs-output")?.textContent ||
      ""
    );
  },

  bindActions(handlers) {
    const root = this.ensure();
    root.querySelector("#hr-agent-analyze").onclick = handlers.analyze;
    root.querySelector("#hr-agent-generate-cv").onclick = handlers.generateCv;
    root.querySelector("#hr-agent-fill").onclick = handlers.fill;
    root.querySelector("#hr-agent-copy").onclick = handlers.copyOutput;
    root.querySelector("#hr-agent-save-context").onclick = handlers.saveContext;
    root.querySelector("#hr-agent-start-backend").onclick = handlers.startBackend;
    root.querySelector("#hr-agent-stop-backend").onclick = handlers.stopBackend;
    root.querySelector("#hr-agent-track-vacancy").onclick = handlers.trackVacancy;
    root.querySelector("#hr-agent-mark-applied").onclick = handlers.markApplied;
    root.querySelector("#hr-agent-open-applications").onclick = handlers.openApplications;
    root.querySelector("#hr-agent-logs").onclick = handlers.showLogs;
    root.querySelector("#hr-agent-logs-refresh").onclick = handlers.refreshLogs;
    root.querySelector("#hr-agent-logs-copy").onclick = handlers.copyLogs;
    root.querySelector("#hr-agent-logs-clear").onclick = handlers.clearLogs;
    root.querySelector("#hr-agent-job-status").onchange = handlers.statusChange;
    root.querySelector("#hr-agent-job-notes").oninput = handlers.notesChange;
  },
};

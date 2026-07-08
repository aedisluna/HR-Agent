window.HrAgentLogger = {
  _entries: [],
  _maxEntries: 200,

  _timestamp() {
    return new Date().toISOString().replace("T", " ").slice(0, 19);
  },

  _persist() {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage(
          {
            type: "SAVE_EXTENSION_LOGS",
            entries: this._entries.slice(-this._maxEntries),
          },
          () => {
            resolve();
          }
        );
      } catch (_error) {
        resolve();
      }
    });
  },

  log(level, message, meta = null) {
    const entry = {
      ts: this._timestamp(),
      level,
      message,
      meta,
    };
    this._entries.push(entry);
    if (this._entries.length > this._maxEntries) {
      this._entries = this._entries.slice(-this._maxEntries);
    }
    void this._persist();
    return entry;
  },

  info(message, meta) {
    return this.log("INFO", message, meta);
  },

  warn(message, meta) {
    return this.log("WARN", message, meta);
  },

  error(message, meta) {
    return this.log("ERROR", message, meta);
  },

  formatEntries(entries) {
    return (entries || [])
      .map((entry) => {
        const meta =
          entry.meta && Object.keys(entry.meta).length
            ? ` | ${JSON.stringify(entry.meta)}`
            : "";
        return `${entry.ts} | ${entry.level} | ${entry.message}${meta}`;
      })
      .join("\n");
  },

  getEntries() {
    return this._entries.slice();
  },

  async loadPersisted() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "GET_EXTENSION_LOGS" }, (response) => {
        const entries = response?.entries || [];
        this._entries = entries.slice(-this._maxEntries);
        resolve(this._entries);
      });
    });
  },

  async clear() {
    this._entries = [];
    await new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "CLEAR_EXTENSION_LOGS" }, () => {
        resolve();
      });
    });
  },
};

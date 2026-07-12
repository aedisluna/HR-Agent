window.HrAgentFrames = {
  _fieldCache: new Map(),

  isTop() {
    return window === window.top;
  },

  registerFrameListener() {
    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message.targetFrameUrl && message.targetFrameUrl !== location.href) {
        return false;
      }

      if (message.type === "HR_AGENT_EXTRACT_FIELDS") {
        sendResponse(this.extractFromThisFrame());
        return true;
      }

      if (message.type === "HR_AGENT_APPLY_MAPPINGS") {
        sendResponse(this.applyInThisFrame(message.mappings || []));
        return true;
      }

      return false;
    });
  },

  makeGlobalId(frameUrl, localId) {
    return `${frameUrl}::${localId}`;
  },

  parseGlobalId(globalId) {
    const splitAt = globalId.indexOf("::");
    if (splitAt <= 0) {
      return { frameUrl: location.href, localId: globalId };
    }
    return {
      frameUrl: globalId.slice(0, splitAt),
      localId: globalId.slice(splitAt + 2),
    };
  },

  extractFromThisFrame() {
    const fields = HrAgentExtractors.extractFormFieldsInAllDocuments();
    this._fieldCache.clear();
    fields.forEach((field) => {
      this._fieldCache.set(field.id, field);
    });

    return {
      frameUrl: location.href,
      fields: fields.map((field) => ({
        id: this.makeGlobalId(location.href, field.id),
        localId: field.id,
        frameUrl: location.href,
        label: field.label,
        field_type: field.field_type,
        name: field.name,
        placeholder: field.placeholder,
        required: field.required,
      })),
    };
  },

  applyInThisFrame(mappings) {
    const results = [];
    for (const mapping of mappings) {
      const localId = mapping.localId || this.parseGlobalId(mapping.field_id).localId;
      const field = this._fieldCache.get(localId);
      if (!field || !mapping.answer) {
        results.push({ ...mapping, filled: false });
        continue;
      }
      if (!mapping.fill) {
        results.push({ ...mapping, filled: false });
        continue;
      }
      const filled = HrAgentFiller.setNativeValue(field.element, mapping.answer);
      results.push({ ...mapping, filled });
    }
    return { frameUrl: location.href, results };
  },

  async broadcast(innerType, payload = {}) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: "HR_AGENT_BROADCAST", innerType, payload }, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        resolve(Array.isArray(response) ? response : []);
      });
    });
  },

  async extractAllFields() {
    if (!this.isTop()) {
      return HrAgentExtractors.extractFormFieldsInAllDocuments();
    }

    const responses = await this.broadcast("HR_AGENT_EXTRACT_FIELDS");
    const merged = [];
    const seen = new Set();

    for (const response of responses) {
      for (const field of response?.fields || []) {
        if (seen.has(field.id)) continue;
        seen.add(field.id);

        const item = { ...field };
        if (response.frameUrl === location.href) {
          item.element = this._fieldCache.get(field.localId)?.element;
        }
        merged.push(item);
      }
    }

    return merged.slice(0, 40);
  },

  async applyAllMappings(mappings) {
    if (!this.isTop()) {
      return HrAgentFiller.applyMappings(
        Array.from(this._fieldCache.values()),
        mappings
      );
    }

    const grouped = new Map();
    for (const mapping of mappings) {
      const parsed = this.parseGlobalId(mapping.field_id);
      const frameUrl = mapping.frameUrl || parsed.frameUrl;
      const localId = mapping.localId || parsed.localId;
      if (!grouped.has(frameUrl)) grouped.set(frameUrl, []);
      grouped.get(frameUrl).push({ ...mapping, localId, frameUrl });
    }

    const allResults = [];
    for (const [frameUrl, frameMappings] of grouped.entries()) {
      const responses = await this.broadcast("HR_AGENT_APPLY_MAPPINGS", {
        mappings: frameMappings,
        targetFrameUrl: frameUrl,
      });
      for (const response of responses) {
        if (response?.frameUrl === frameUrl) {
          allResults.push(...(response.results || []));
        }
      }
    }

    return allResults;
  },
};

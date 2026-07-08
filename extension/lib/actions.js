window.HrAgentActions = {
  async ensureBackendReady() {
    const status = await HrAgentBackend.refreshStatus();
    if (!status.backend) {
      throw new Error("Backend is offline. Press Start backend first.");
    }
  },

  async startBackend() {
    HrAgentPanel.setStatus("Starting backend…", "busy");
    try {
      await HrAgentBackend.startBackend();
      await HrAgentBackend.refreshStatus();
      HrAgentPanel.setStatus("Backend is online.", "success");
      HrAgentLogger.info("Backend started");
    } catch (error) {
      HrAgentPanel.setStatus(error.message, "error");
      HrAgentLogger.error("Backend start failed", { error: error.message });
    }
  },

  async stopBackend() {
    HrAgentPanel.setStatus("Stopping backend…", "busy");
    try {
      await HrAgentBackend.stopBackend();
      await HrAgentBackend.refreshStatus();
      HrAgentPanel.setStatus("Backend stopped.");
      HrAgentLogger.info("Backend stopped");
    } catch (error) {
      HrAgentPanel.setStatus(error.message);
      HrAgentLogger.error("Backend stop failed", { error: error.message });
    }
  },

  async initPanel(payload = {}) {
    HrAgentPanel.ensure();
    await HrAgentBackend.refreshStatus();
    try {
      await HrAgentJobCard.refresh(payload);
    } catch (_error) {
      // backend may still be offline on first open
    }
    try {
      await HrAgentQuestions.showMissingProfileQuestions();
    } catch (_error) {
      // backend may still be offline on first open
    }
  },

  withLanguage(payload) {
    return {
      ...payload,
      response_language: HrAgentPanel.getLanguage(),
    };
  },

  async copyOutput() {
    const text = HrAgentPanel.getOutput();
    if (!text) {
      HrAgentPanel.setStatus("Nothing to copy yet.");
      return;
    }
    await navigator.clipboard.writeText(text);
    HrAgentPanel.setStatus("Copied to clipboard.");
  },

  async analyze(payload) {
    await this.ensureBackendReady();
    const requestPayload = this._payloadForRequest(payload);
    if (
      requestPayload.platform === "linkedin" &&
      (!requestPayload.role || (requestPayload.job_text || "").length < 200)
    ) {
      HrAgentPanel.setStatus(
        "LinkedIn: select a vacancy in the right panel so title and description load.",
        "error"
      );
      HrAgentLogger.warn("LinkedIn analyze blocked: incomplete extraction", {
        role: requestPayload.role,
        job_text_chars: requestPayload.job_text?.length || 0,
        url: requestPayload.url,
      });
      return;
    }
    HrAgentPanel.setStatus("Analyzing vacancy…", "busy");
    HrAgentLogger.info("Analyze started", { platform: requestPayload.platform, url: requestPayload.url });
    try {
      const result = await HrAgentApi.analyzePage(
        this.withLanguage({ ...requestPayload, save_application: true })
      );
      const fit = result.analysis?.fit_score ?? "n/a";
      const apply = result.analysis?.should_apply;
      HrAgentPanel.setOutput(
        [
          `Fit score: ${fit}${apply ? ` · Apply: ${apply}` : ""}`,
          "",
          result.analysis?.result || "",
          "",
          result.cover_letter
            ? `Cover letter:\n${result.cover_letter}`
            : "Cover letter: skipped (faster analyze). Use Fill form or ask separately.",
        ].join("\n")
      );
      HrAgentJobCard.updateFromAnalyze(result, requestPayload);
      HrAgentPanel.setStatus("Analysis complete · vacancy saved.", "success");
      if (result.questions?.length) {
        HrAgentQuestions.showFromAnalysis(result.questions);
      } else {
        await HrAgentQuestions.showMissingProfileQuestions();
      }
      await HrAgentApi.saveJobContext(requestPayload);
      HrAgentLogger.info("Analyze finished", { fit_score: fit });
    } catch (error) {
      HrAgentLogger.error("Analyze failed", { error: error.message });
      throw error;
    }
  },

  async generateCv(payload) {
    await this.ensureBackendReady();
    const requestPayload = this._payloadForRequest(payload);
    HrAgentPanel.setStatus("Generating CV…", "busy");
    HrAgentLogger.info("Generate CV started", { platform: requestPayload.platform, url: requestPayload.url });
    try {
      const result = await HrAgentApi.generateCv(
        this.withLanguage({ ...requestPayload, save_application: false })
      );
      const cv = result.cv || "";
      HrAgentPanel.setOutput(cv);

      const fields = this._extractFields(requestPayload);
      const inserted = HrAgentFiller.fillCoverLetterFields(fields, cv);
      if (inserted) {
        HrAgentPanel.setStatus(`CV ready — inserted into ${inserted} field(s). Review before submit.`, "success");
      } else {
        HrAgentPanel.setStatus("CV ready — review and copy.", "success");
      }
      HrAgentLogger.info("Generate CV finished", {
        chars: cv.length,
        inserted_fields: inserted,
      });
    } catch (error) {
      HrAgentLogger.error("Generate CV failed", { error: error.message });
      throw error;
    }
  },

  async fillForm(payload, fields, platformLabel) {
    await this.ensureBackendReady();
    const requestPayload = this._payloadForRequest(payload);
    if (!fields.length) {
      HrAgentPanel.setStatus("No form fields detected.");
      HrAgentLogger.warn("Fill form: no fields detected", { platform: platformLabel });
      return;
    }

    HrAgentLogger.info("Fill form started", {
      platform: platformLabel,
      fields: fields.length,
      labels: fields.map((field) => field.label).slice(0, 8),
    });

    HrAgentQuestions.rememberFields(fields);
    HrAgentPanel.setStatus("Filling form…", "busy");
    try {
      const mappings = await HrAgentApi.fillForm(
        this.withLanguage({
          job_text: requestPayload.job_text,
          platform: requestPayload.platform,
          url: requestPayload.url,
          title: requestPayload.title,
          company: requestPayload.company,
          role: requestPayload.role,
          fields: HrAgentExtractors.serializeFields(fields),
          use_llm: true,
        })
      );

      const filled = HrAgentFiller.applyMappings(fields, mappings.mappings);
      const lines = filled.map((item) => {
        const status = item.filled ? "FILLED" : item.answer ? "REVIEW" : "MISSING";
        return `[${status}] ${item.label}\n${item.answer || ""}`;
      });

      HrAgentPanel.setOutput(lines.join("\n\n"));
      HrAgentPanel.setStatus(
        `${platformLabel}: ${mappings.auto_fill_count} filled, ${mappings.review_count} to review.`,
        "success"
      );
      await HrAgentQuestions.showFromMappings(mappings.mappings);
      const tracked = await this.trackVacancy(requestPayload, {
        status: HrAgentPanel.getJobStatus() || "draft",
        silent: true,
      });
      if (tracked) HrAgentJobCard.applyApplication(tracked);
      HrAgentLogger.info("Fill form finished", {
        auto_fill: mappings.auto_fill_count,
        review: mappings.review_count,
      });
    } catch (error) {
      HrAgentLogger.error("Fill form failed", { error: error.message });
      throw error;
    }
  },

  async openApplications() {
    window.open(HrAgentApi.APPLICATIONS_UI_URL, "_blank", "noopener,noreferrer");
    HrAgentPanel.setStatus("Applications page opened.");
    HrAgentLogger.info("Opened applications dashboard");
  },

  async trackVacancy(payload, options = {}) {
    if (!options.silent) {
      await this.ensureBackendReady();
      HrAgentPanel.setStatus("Saving vacancy...");
    } else {
      try {
        await HrAgentApi.health();
      } catch (_error) {
        return null;
      }
    }

    const result = await HrAgentApi.trackApplication({
      platform: payload.platform,
      url: payload.url,
      title: payload.title,
      company: payload.company,
      role: payload.role,
      job_text: payload.job_text,
      status: options.status || "draft",
      fit_score: options.fit_score,
      notes:
        options.notes !== undefined ? options.notes : HrAgentPanel.getNotes() || undefined,
    });

    if (!options.silent) {
      HrAgentPanel.setStatus("Vacancy saved.");
      HrAgentJobCard.applyApplication(result);
    }
    HrAgentLogger.info("Vacancy tracked", {
      status: options.status || "draft",
      url: payload.url,
    });
    return result;
  },

  async markApplied(payload) {
    await this.ensureBackendReady();
    HrAgentPanel.setStatus("Marking as applied...");
    const result = await this.trackVacancy(this._payloadForRequest(payload), { status: "applied" });
    HrAgentPanel.setJobStatus("applied");
    if (result) HrAgentJobCard.applyApplication(result);
    HrAgentPanel.setStatus("Marked as applied.", "success");
  },

  bindContentHandlers(payload) {
    const onError = (error) => {
      HrAgentPanel.setStatus(error.message, "error");
    };

    return {
      analyze: () => this.analyze(payload).catch(onError),
      generateCv: () => this.generateCv(payload).catch(onError),
      fill: () => this.fillForm(payload, this._extractFields(payload), this._platformLabel(payload)).catch(onError),
      copyOutput: () => this.copyOutput().catch(onError),
      saveContext: async () => {
        await HrAgentApi.saveJobContext(payload);
        HrAgentPanel.setStatus("Job context saved.");
      },
      startBackend: () => this.startBackend(),
      stopBackend: () => this.stopBackend(),
      trackVacancy: () => this.trackVacancy(this._payloadForRequest(payload)).catch(onError),
      markApplied: () => this.markApplied(payload).catch(onError),
      openApplications: () => this.openApplications(),
      showLogs: () => this.showLogs().catch(onError),
      refreshLogs: () => this.refreshLogs().catch(onError),
      copyLogs: () => this.copyLogs().catch(onError),
      clearLogs: () => this.clearLogs().catch(onError),
      statusChange: () =>
        HrAgentJobCard.changeStatus(payload, HrAgentPanel.getJobStatus()).catch(onError),
      notesChange: () => HrAgentJobCard.scheduleNotesSave(payload),
    };
  },

  _platformLabel(payload) {
    if (payload.platform === "hh") return "HH.ru";
    if (payload.platform === "linkedin") return "LinkedIn";
    return payload.platform || "ATS";
  },

  _extractFields(payload) {
    if (payload.platform === "hh") {
      return HrAgentExtractors.extractHhFormFields();
    }
    return HrAgentExtractors.extractFormFields();
  },

  _payloadForRequest(payload) {
    if (payload.platform === "linkedin") {
      return HrAgentExtractors.extractLinkedInJob(payload);
    }

    if (payload.platform !== "hh") return payload;

    const role =
      HrAgentExtractors.textFromSelectors([
        "[data-qa='vacancy-title']",
        "h1.vacancy-title",
        "[data-qa='vacancy-response-popup-title']",
        "h1",
      ]) || payload.role;
    const company =
      HrAgentExtractors.textFromSelectors([
        "[data-qa='vacancy-company-name']",
        ".vacancy-company-name",
        "[data-qa='vacancy-response-popup-company-name']",
      ]) || payload.company;

    return {
      ...payload,
      role,
      company,
      title: role || payload.title,
    };
  },

  async refreshLogs(includeServer = true) {
    const sections = [];

    await HrAgentLogger.loadPersisted();
    const extensionText = HrAgentLogger.formatEntries(HrAgentLogger.getEntries());
    sections.push("=== Extension ===");
    sections.push(extensionText || "(no extension logs yet)");

    if (includeServer) {
      try {
        const backendLogs = await HrAgentApi.getLogs("all", 200);
        sections.push("");
        sections.push("=== Backend ===");
        sections.push(
          backendLogs.backend?.entries?.join("\n") || "(backend log file is empty)"
        );
        sections.push("");
        sections.push("=== Launcher ===");
        sections.push(
          backendLogs.launcher?.entries?.join("\n") || "(launcher log file is empty)"
        );
      } catch (error) {
        sections.push("");
        sections.push("=== Backend/Launcher ===");
        sections.push(`Failed to load server logs: ${error.message}`);
        HrAgentLogger.error("Failed to load server logs", { error: error.message });
      }
    }

    HrAgentPanel.setLogs(sections.join("\n"));
    HrAgentPanel.setStatus("Logs refreshed.", "success");
  },

  async showLogs() {
    const shouldOpen = HrAgentPanel.toggleLogsPanel(true);
    if (shouldOpen) {
      await this.refreshLogs();
      HrAgentPanel.setStatus("Logs opened.", "default");
    }
  },

  async copyLogs() {
    let text = HrAgentPanel.getLogs();
    if (!text) {
      await this.refreshLogs();
      text = HrAgentPanel.getLogs();
    }
    if (!text) {
      HrAgentPanel.setStatus("No logs to copy yet.", "error");
      return;
    }
    await navigator.clipboard.writeText(text);
    HrAgentPanel.setStatus("Logs copied to clipboard.", "success");
  },

  async clearLogs() {
    await HrAgentLogger.clear();
    try {
      await HrAgentApi.clearLogs("all");
    } catch (_error) {
      // Backend offline — extension logs still cleared.
    }
    HrAgentPanel.setLogs("");
    HrAgentPanel.setStatus("All logs cleared.", "success");
  },
};

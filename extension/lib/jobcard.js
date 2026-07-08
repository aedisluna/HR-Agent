window.HrAgentJobCard = {
  _applicationId: null,
  _notesTimer: null,

  async refresh(payload) {
    const requestPayload = HrAgentActions._payloadForRequest(payload);
    HrAgentPanel.setJobTitle(
      requestPayload.company || "Company",
      requestPayload.role || requestPayload.title || "Role",
      HrAgentActions._platformLabel(requestPayload)
    );

    const salary = HrAgentExtractors.extractSalary();
    HrAgentPanel.setSalary(salary);

    const keywords = HrAgentExtractors.extractTopKeywords(requestPayload.job_text);
    HrAgentPanel.setKeywords(keywords);

    try {
      const data = await HrAgentApi.getApplicationByUrl(requestPayload.url);
      this.applyApplication(data?.application || null);
    } catch (_error) {
      this.applyApplication(null);
    }
  },

  applyApplication(application) {
    this._applicationId = application?.id || null;
    HrAgentPanel.setFitScore(application?.fit_score ?? null);
    HrAgentPanel.setJobStatus(application?.status || "draft");
    HrAgentPanel.setNotes(application?.notes || "", { silent: true });
  },

  updateFromAnalyze(result, payload) {
    const fit = result.analysis?.fit_score;
    if (fit != null) {
      HrAgentPanel.setFitScore(fit);
    }

    const keywords = HrAgentExtractors.extractTopKeywords(payload.job_text);
    if (keywords.length) {
      HrAgentPanel.setKeywords(keywords);
    }

    if (result.application) {
      this.applyApplication(result.application);
    }
  },

  async saveNotes(payload, notes) {
    if (!this._applicationId) {
      await HrAgentActions.trackVacancy(HrAgentActions._payloadForRequest(payload), {
        status: HrAgentPanel.getJobStatus(),
        notes,
        silent: true,
      });
      await this.refresh(payload);
      return;
    }

    await HrAgentApi.updateApplication(this._applicationId, { notes });
  },

  scheduleNotesSave(payload) {
    clearTimeout(this._notesTimer);
    this._notesTimer = setTimeout(() => {
      const notes = HrAgentPanel.getNotes();
      this.saveNotes(payload, notes).catch(() => {
        HrAgentPanel.setStatus("Could not save notes.", "error");
      });
    }, 600);
  },

  async changeStatus(payload, status) {
    const requestPayload = HrAgentActions._payloadForRequest(payload);
    HrAgentPanel.setJobStatus(status);

    if (this._applicationId) {
      await HrAgentApi.updateApplication(this._applicationId, { status });
      return;
    }

    await HrAgentActions.trackVacancy(requestPayload, {
      status,
      notes: HrAgentPanel.getNotes() || undefined,
      silent: true,
    });
    await this.refresh(requestPayload);
  },
};

window.HrAgentQuestions = {
  _fieldsById: new Map(),
  _items: [],

  rememberFields(fields) {
    this._fieldsById = new Map(
      (fields || []).map((field) => [field.id, field.element || field])
    );
  },

  async loadMissingQuestions() {
    return HrAgentApi.request("/extension/missing-questions");
  },

  async saveAnswer(question, answer, options = {}) {
    return HrAgentApi.saveAnswer({
      question_pattern: question,
      answer,
      confidence: options.confidence || "high",
      requires_confirmation: options.requires_confirmation ?? false,
    });
  },

  render(questions, options = {}) {
    const container = HrAgentPanel.ensure().querySelector("#hr-agent-questions");
    this._items = questions || [];
    container.innerHTML = "";

    HrAgentPanel.setQuestionsCount(this._items.length);

    if (!this._items.length) {
      container.innerHTML = `<div class="hr-agent-question-empty">No pending questions.</div>`;
      HrAgentPanel.toggleCollapsible("hr-agent-questions-section", false);
      return;
    }

    const expand = options.expand ?? this._items.length <= 2;
    HrAgentPanel.toggleCollapsible("hr-agent-questions-section", expand);

    this._items.forEach((item, index) => {
      const block = document.createElement("div");
      block.className = "hr-agent-question-block";
      block.innerHTML = `
        <div class="hr-agent-question-text">${HrAgentExtractors.escapeHtml(item.question)}</div>
        ${
          item.current_assumption
            ? `<div class="hr-agent-question-hint">${HrAgentExtractors.escapeHtml(item.current_assumption)}</div>`
            : ""
        }
        <div class="hr-agent-question-row">
          <textarea rows="2" data-question-index="${index}" placeholder="Your answer">${HrAgentExtractors.escapeHtml(item.suggested_answer || "")}</textarea>
          <button type="button" class="btn-save" data-save-index="${index}">Save</button>
        </div>
      `;
      container.appendChild(block);
    });

    container.querySelectorAll("textarea[data-question-index]").forEach((textarea) => {
      textarea.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
          event.preventDefault();
          const index = Number(textarea.getAttribute("data-question-index"));
          container.querySelector(`button[data-save-index="${index}"]`)?.click();
        }
      });
    });

    container.querySelectorAll("button[data-save-index]").forEach((button) => {
      button.addEventListener("click", async () => {
        const index = Number(button.getAttribute("data-save-index"));
        const item = this._items[index];
        const textarea = container.querySelector(
          `textarea[data-question-index="${index}"]`
        );
        const answer = textarea?.value?.trim();
        if (!answer) {
          HrAgentPanel.setStatus("Enter an answer before saving.", "error");
          return;
        }

        button.disabled = true;
        try {
          await this.saveAnswer(item.question, answer, {
            confidence: "high",
            requires_confirmation: false,
          });

          const fieldElement = this._fieldsById.get(item.field_id);
          if (fieldElement) {
            HrAgentFiller.setNativeValue(fieldElement, answer);
          }

          this._items.splice(index, 1);
          this.render(this._items, { expand: true });
          HrAgentPanel.setStatus("Answer saved.", "success");
        } catch (error) {
          button.disabled = false;
          HrAgentPanel.setStatus(error.message, "error");
        }
      });
    });
  },

  async showFromMappings(mappings) {
    const questions = (mappings || [])
      .filter((item) => !item.fill)
      .map((item) => ({
        id: item.field_id || item.label,
        question: item.label,
        suggested_answer: item.answer || "",
        current_assumption: item.answer || "",
        source: "form_mapping",
        field_id: item.field_id,
      }))
      .filter(
        (item) =>
          item.question &&
          !HrAgentExtractors.isPlaceholderLabel(item.question) &&
          item.question !== "Unknown field"
      );
    this.render(questions, { expand: true });
  },

  async showFromAnalysis(questions) {
    const items = (questions || [])
      .map((item, index) => {
        if (typeof item === "string") {
          return {
            id: `analysis-${index}`,
            question: item,
            suggested_answer: "",
            current_assumption: "",
            source: "analysis",
          };
        }
        return {
          id: item.id || `analysis-${index}`,
          question: item.question,
          suggested_answer: item.suggested_answer || "",
          current_assumption: item.current_assumption || "",
          source: item.source || "analysis",
          field_id: item.field_id,
        };
      })
      .filter((item) => item.question);
    this.render(items, { expand: true });
  },

  async showMissingProfileQuestions() {
    const result = await this.loadMissingQuestions();
    this.render(result.questions || [], { expand: false });
  },
};

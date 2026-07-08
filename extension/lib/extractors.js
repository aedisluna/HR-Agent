window.HrAgentExtractors = {
  textFromSelectors(selectors, root = document) {
    for (const selector of selectors) {
      const element = root.querySelector(selector);
      const text = element?.innerText?.trim() || element?.textContent?.trim();
      if (text) return text;
    }
    return "";
  },

  findLinkedInJobDetailsRoot() {
    const roots = [
      ".jobs-search__job-details",
      ".jobs-details__main-content",
      ".job-view-layout",
      ".jobs-details",
      ".scaffold-layout__detail",
      "[class*='job-details-jobs-unified-top-card']",
    ];
    for (const selector of roots) {
      const element = document.querySelector(selector);
      if (element) return element;
    }
    return document;
  },

  extractLinkedInJob(fallback = {}) {
    const detailRoot = this.findLinkedInJobDetailsRoot();
    const role =
      this.textFromSelectors(
        [
          ".job-details-jobs-unified-top-card__job-title",
          "[class*='job-details-jobs-unified-top-card__job-title']",
          ".jobs-unified-top-card__job-title",
          "[class*='jobs-unified-top-card__job-title']",
          "h1.t-24",
          "h1",
        ],
        detailRoot
      ) ||
      this.textFromSelectors([
        ".top-card-layout__title",
        "h1.top-card-layout__title",
        "[class*='job-details-jobs-unified-top-card__job-title']",
      ]);

    const company =
      this.textFromSelectors(
        [
          ".job-details-jobs-unified-top-card__company-name a",
          ".job-details-jobs-unified-top-card__company-name",
          "[class*='job-details-jobs-unified-top-card__company-name'] a",
          "[class*='job-details-jobs-unified-top-card__company-name']",
          ".jobs-unified-top-card__company-name a",
          ".jobs-unified-top-card__company-name",
          ".jobs-unified-top-card__subtitle-primary-grouping a",
          "a[data-tracking-control-name*='org-name']",
          ".topcard__org-name-link",
        ],
        detailRoot
      ) ||
      this.textFromSelectors([
        "a.topcard__org-name-link",
        "[class*='company-name'] a",
        "[class*='company-name']",
      ]);

    const jobText = this.collectLinkedInJobText(detailRoot);
    const url = location.href;

    return {
      platform: "linkedin",
      url,
      title: role || fallback.title || "",
      company: company || fallback.company || "",
      role: role || fallback.role || "",
      job_text: this.formatJobTextForAnalysis({
        role: role || fallback.role || "",
        company: company || fallback.company || "",
        job_text: jobText || fallback.job_text || "",
      }),
      page_kind: role || jobText ? "job" : "unknown",
    };
  },

  collectLinkedInJobText(detailRoot = null) {
    const root = detailRoot || this.findLinkedInJobDetailsRoot();
    const selectors = [
      "#job-details",
      ".jobs-description__content",
      ".jobs-description-content__text",
      "[class*='jobs-description__content']",
      "[class*='jobs-description-content']",
      ".jobs-box__html-content",
      "div.description__text",
      ".job-view-layout .jobs-box__html-content",
    ];

    for (const selector of selectors) {
      const element = (root === document ? document : root).querySelector(selector);
      const text = element?.innerText?.trim();
      if (text && text.length > 120) return text;
    }

    if (root !== document) {
      const panelText = root.innerText?.trim();
      if (panelText && panelText.length > 200) {
        return panelText;
      }
    }

    return "";
  },

  formatJobTextForAnalysis(payload) {
    const parts = [];
    if (payload.role) parts.push(`Job title: ${payload.role}`);
    if (payload.company) parts.push(`Company: ${payload.company}`);
    if (payload.job_text) parts.push(payload.job_text);
    return parts.join("\n\n").trim();
  },

  collectJobText(platform = "") {
    if (platform === "linkedin") {
      return this.extractLinkedInJob().job_text;
    }

    const selectors = [
      ".jobs-description__content",
      "#job-details",
      ".job-view-layout .jobs-box__html-content",
      ".vacancy-description",
      "[data-qa='vacancy-description']",
      ".posting-page",
      ".content",
    ];

    for (const selector of selectors) {
      const element = document.querySelector(selector);
      const text = element?.innerText?.trim();
      if (text && text.length > 120) return text;
    }

    const main = document.querySelector("main, article");
    const mainText = main?.innerText?.trim();
    if (mainText && mainText.length > 120) return mainText;

    return document.body.innerText.slice(0, 12000).trim();
  },

  extractSalary() {
    const fromDom = this.textFromSelectors([
      "[data-qa='vacancy-salary']",
      "[data-qa='vacancy-salary-compensation']",
      ".vacancy-salary",
    ]);
    if (fromDom) return fromDom.replace(/\s+/g, " ").trim();

    const jobText = this.collectJobText();
    const patterns = [
      /(\d[\d\s]{2,6})\s*(?:–|—|-)\s*(\d[\d\s]{2,6})\s*₽/,
      /от\s+(\d[\d\s]+)\s*(?:до|–|—|-)\s*(\d[\d\s]+)/i,
      /(\d{2,3}\s?\d{3})\s*(?:–|—|-)\s*(\d{2,3}\s?\d{3})\s*(?:₽|руб)/i,
    ];
    for (const pattern of patterns) {
      const match = jobText.match(pattern);
      if (match) {
        return match[0].replace(/\s+/g, " ").trim();
      }
    }
    return "";
  },

  extractTopKeywords(jobText, limit = 10) {
    const text = String(jobText || "").toLowerCase();
    if (!text) return [];

    const candidates = [
      "Postman",
      "Swagger",
      "PostgreSQL",
      "MS SQL",
      "SQL",
      "Selenium",
      "Cypress",
      "Playwright",
      "Python",
      "Java",
      "JavaScript",
      "TypeScript",
      "REST API",
      "API testing",
      "Docker",
      "Kubernetes",
      "Jira",
      "TestIT",
      "Agile",
      "Scrum",
      "React",
      "C#",
      "automation",
      "regression",
      "manual testing",
      "web testing",
      "CI/CD",
      "Git",
      "FinTech",
      "mobile testing",
    ];

    const matched = [];
    for (const keyword of candidates) {
      if (text.includes(keyword.toLowerCase())) {
        matched.push(keyword);
      }
    }
    return matched.slice(0, limit);
  },

  isApplicationLikePage() {
    const text = document.body.innerText.toLowerCase();
    const keywords = [
      "apply",
      "application",
      "resume",
      "cover letter",
      "отклик",
      "резюме",
      "сопроводительное",
      "вакансия",
    ];
    const fields = this.extractFormFields();
    const keywordHits = keywords.filter((word) => text.includes(word)).length;
    return fields.length >= 3 && keywordHits >= 1;
  },

  isPlaceholderLabel(text) {
    if (!text) return true;
    const normalized = text.trim().toLowerCase();
    const placeholders = [
      "писать тут",
      "write here",
      "your answer",
      "введите ответ",
      "enter your answer",
      "unknown field",
      "сгенерировать",
    ];
    return placeholders.includes(normalized) || normalized.length < 12;
  },

  isCoverLetterField(label) {
    const normalized = String(label || "").trim().toLowerCase();
    if (!normalized) return false;
    return (
      normalized.includes("сопровод") ||
      normalized.includes("cover letter") ||
      normalized.includes("covering letter") ||
      normalized.includes("motivation letter")
    );
  },

  findQuestionText(element) {
    if (!element) return "";

    const aria = element.getAttribute("aria-label");
    if (aria && !this.isPlaceholderLabel(aria) && !aria.startsWith("task_")) {
      return aria.trim();
    }

    const labelledBy = element.getAttribute("aria-labelledby");
    if (labelledBy) {
      const labelText = labelledBy
        .split(" ")
        .map((id) => document.getElementById(id)?.innerText?.trim())
        .filter(Boolean)
        .join(" ");
      if (labelText && !this.isPlaceholderLabel(labelText)) return labelText;
    }

    const taskContainer = element.closest(
      "[data-qa='task-body'], [data-qa='vacancy-response-popup-additional-question'], [data-qa='vacancy-response-popup-body'], .vacancy-response-popup-body, .magritte-redesign"
    );
    if (taskContainer) {
      const questionSelectors = [
        "[data-qa='task-question']",
        "[data-qa='vacancy-response-popup-question']",
        ".vacancy-response-popup-question",
        ".bloko-form-item__label",
        "label",
      ];
      for (const selector of questionSelectors) {
        const questionNode = taskContainer.querySelector(selector);
        if (!questionNode || questionNode.contains(element)) continue;
        const text = questionNode.innerText?.trim().replace(/\s+/g, " ");
        if (text && !this.isPlaceholderLabel(text)) return text;
      }
    }

    const hhQuestion = element
      .closest("[data-qa='task-body'], [data-qa='vacancy-response-popup-body'], .vacancy-response-popup-body, form")
      ?.querySelector("[data-qa='task-question'], [data-qa='vacancy-response-popup-question']");
    if (hhQuestion) {
      const text = hhQuestion.innerText.trim();
      if (text && !this.isPlaceholderLabel(text)) return text.replace(/\s+/g, " ");
    }

    let previous = element.previousElementSibling;
    for (let step = 0; step < 6 && previous; step += 1) {
      const text = previous.innerText?.trim();
      if (
        text &&
        !this.isPlaceholderLabel(text) &&
        text.length <= 500 &&
        !previous.querySelector("textarea, input, select, button")
      ) {
        return text.replace(/\s+/g, " ");
      }
      previous = previous.previousElementSibling;
    }

    let current = element.parentElement;
    for (let depth = 0; depth < 10 && current; depth += 1) {
      const children = Array.from(current.children);
      const fieldNode = element.closest("textarea, input, select") || element;
      const index = children.findIndex((child) => child === fieldNode || child.contains(fieldNode));

      for (let i = index - 1; i >= 0; i -= 1) {
        const sibling = children[i];
        const siblingText = sibling.innerText?.trim();
        if (
          siblingText &&
          !this.isPlaceholderLabel(siblingText) &&
          siblingText.length <= 500 &&
          !sibling.querySelector("textarea, input, select, button")
        ) {
          return siblingText.replace(/\s+/g, " ");
        }
      }

      const questionNode = current.querySelector(
        "[data-qa='task-question'], [data-qa='vacancy-response-popup-question'], .vacancy-response-popup-question"
      );
      if (questionNode && !questionNode.contains(element)) {
        const text = questionNode.innerText?.trim();
        if (text && !this.isPlaceholderLabel(text)) {
          return text.replace(/\s+/g, " ");
        }
      }

      current = current.parentElement;
    }

    return "";
  },

  extractHhFormFields() {
    const fields = [];
    const seen = new Set();

    const addField = (element, label) => {
      if (!element || element.disabled || element.type === "hidden") return;
      const id = element.id || element.name || `field-${fields.length + 1}`;
      if (seen.has(id)) return;
      seen.add(id);

      const resolvedLabel =
        label ||
        this.findQuestionText(element) ||
        element.getAttribute("data-qa") ||
        element.name ||
        element.id ||
        "";

      if (!resolvedLabel || this.isPlaceholderLabel(resolvedLabel)) return;

      fields.push({
        id,
        label: resolvedLabel.replace(/\s+/g, " ").trim(),
        field_type: element.type || element.tagName.toLowerCase(),
        name: element.name || null,
        placeholder: element.placeholder || null,
        required: element.required || element.getAttribute("aria-required") === "true",
        element,
      });
    };

    const taskContainers = document.querySelectorAll(
      "[data-qa='task-body'], [data-qa='vacancy-response-popup-additional-question']"
    );
    taskContainers.forEach((container) => {
      const input = container.querySelector(
        "textarea, input:not([type='hidden']):not([type='checkbox']):not([type='radio']), select"
      );
      if (!input) return;

      const questionNode = container.querySelector(
        "[data-qa='task-question'], [data-qa='vacancy-response-popup-question'], .vacancy-response-popup-question, .bloko-form-item__label, label"
      );
      const label = questionNode?.innerText?.trim() || this.findQuestionText(input);
      addField(input, label);
    });

    document
      .querySelectorAll(
        "textarea[id*='task_'], textarea[name*='task_'], textarea[data-qa*='letter'], textarea[data-qa*='response']"
      )
      .forEach((element) => addField(element, this.findQuestionText(element)));

    document
      .querySelectorAll(
        "[data-qa='vacancy-response-popup-form-letter-input'] textarea, textarea[name='letter'], textarea[data-qa*='letter']"
      )
      .forEach((element) =>
        addField(element, "Сопроводительное письмо")
      );

    document
      .querySelectorAll(
        "[data-qa='vacancy-response-popup-form-letter'], [data-qa*='letter-input'], [data-qa='vacancy-response-letter']"
      )
      .forEach((block) => {
        const textarea = block.matches("textarea")
          ? block
          : block.querySelector("textarea");
        if (textarea) addField(textarea, "Сопроводительное письмо");
      });

    document
      .querySelectorAll(
        "[data-qa='vacancy-response-popup'], [data-qa='response-popup'], .magritte-modal, .vacancy-response-popup"
      )
      .forEach((popup) => {
        popup.querySelectorAll("textarea").forEach((textarea) => {
          const container =
            textarea.closest("[data-qa*='letter'], .bloko-form-item, label") ||
            textarea.parentElement;
          const labelText = container?.innerText?.trim() || "";
          if (
            labelText.toLowerCase().includes("сопровод") ||
            this.isCoverLetterField(labelText)
          ) {
            addField(textarea, "Сопроводительное письмо");
          }
        });
      });

    if (!fields.length) {
      const popup = document.querySelector(
        "[data-qa='vacancy-response-popup'], [data-qa='vacancy-response-popup-body'], .vacancy-response-popup"
      );
      popup?.querySelectorAll("textarea").forEach((element) => {
        addField(element, this.findQuestionText(element));
      });
    }

    if (!fields.length) {
      return this.extractFormFields();
    }

    return fields.slice(0, 40);
  },

  extractFormFields() {
    const fields = [];
    const seen = new Set();

    const addField = (element, label) => {
      if (!element || element.disabled || element.type === "hidden") return;

      const id =
        element.id ||
        element.name ||
        `field-${fields.length + 1}-${label.slice(0, 20).replace(/\s+/g, "-")}`;

      if (seen.has(id)) return;
      seen.add(id);

      fields.push({
        id,
        label: label || element.name || element.id || "Unknown field",
        field_type: element.type || element.tagName.toLowerCase(),
        name: element.name || null,
        placeholder: element.placeholder || null,
        required: element.required || element.getAttribute("aria-required") === "true",
        element,
      });
    };

    document.querySelectorAll("label").forEach((label) => {
      const text = label.innerText.trim();
      const htmlFor = label.getAttribute("for");
      if (!text) return;

      if (htmlFor) {
        const linked = document.getElementById(htmlFor);
        addField(linked, text);
        return;
      }

      const nested = label.querySelector("input, textarea, select");
      addField(nested, text);
    });

    document.querySelectorAll("input, textarea, select").forEach((element) => {
      const aria = element.getAttribute("aria-label");
      const question = this.findQuestionText(element);
      const label = question || aria || element.name || element.id;
      if (this.isPlaceholderLabel(label)) return;
      addField(element, label);
    });

    return fields.slice(0, 40);
  },

  serializeFields(fields) {
    return fields.map(({ id, label, field_type, name, placeholder, required }) => ({
      id,
      label,
      field_type,
      name,
      placeholder,
      required,
    }));
  },

  escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  },
};

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

    const jsonLd = this.extractJsonLdJobPosting();
    if (jsonLd?.description) {
      const description = String(jsonLd.description).replace(/<[^>]+>/g, " ").trim();
      if (description.length >= 120) return description;
    }

    const selectors = [
      ".job__description",
      ".job-description",
      ".job-post",
      ".posting-page",
      "[class*='job-description']",
      "[class*='JobDescription']",
      "[data-qa='vacancy-description']",
      ".vacancy-description",
      "#job-details",
      ".jobs-description__content",
      ".job-view-layout .jobs-box__html-content",
    ];

    for (const selector of selectors) {
      const element = document.querySelector(selector);
      const text = element?.innerText?.trim();
      if (text && text.length >= 120) return text;
    }

    if (this.isCareersHubPage()) {
      return "";
    }

    const main = document.querySelector("main, article");
    const mainText = main?.innerText?.trim();
    if (mainText && mainText.length >= 120 && this.isVacancyDetailPage(mainText)) {
      return mainText;
    }

    const bodyText = document.body.innerText.slice(0, 12000).trim();
    return this.isVacancyDetailPage(bodyText) ? bodyText : "";
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

  isJobLikePage() {
    if (this.extractJsonLdJobPosting()) return true;
    if (this.isVacancyDetailPage()) return true;
    return false;
  },

  isMarketingRoleTitle(text) {
    const normalized = String(text || "").trim().toLowerCase();
    if (!normalized || normalized.length > 120) return true;
    const patterns = [
      /^make a real impact/,
      /^join (our|the) team/,
      /^careers$/,
      /^open roles$/,
      /^we['’]?re hiring/,
      /^view open roles/,
      /heart health\.?$/,
      /^ready to do the most meaningful work/,
      /^help thousands of hearts/,
    ];
    return patterns.some((pattern) => pattern.test(normalized));
  },

  isCareersHubPage(text = "") {
    const body = (text || document.body.innerText || "").toLowerCase();
    const url = location.href.toLowerCase();
    const hubMarkers = [
      "culture and values",
      "who we are",
      "view open roles",
      "our core values",
      "open roles",
      "what we do",
      "for businesses",
      "for individuals",
    ];
    const hubHits = hubMarkers.filter((marker) => body.includes(marker)).length;
    const onCareersPath = /\/careers\b/.test(url) && !/\/jobs?\//.test(url);
    const hasGhJobIdOnly = /[?&]gh_jid=/.test(url) && onCareersPath;
    return hubHits >= 2 || hasGhJobIdOnly || (onCareersPath && hubHits >= 1);
  },

  isVacancyDetailPage(text = "") {
    const body = (text || document.body.innerText || "").toLowerCase();
    if (this.isCareersHubPage(body)) return false;

    const detailMarkers = [
      "responsibilities",
      "requirements",
      "qualifications",
      "what you'll do",
      "what you will do",
      "who you are",
      "about the role",
      "about the job",
      "job description",
      "обязанности",
      "требования",
      "описание вакансии",
    ];
    const detailHits = detailMarkers.filter((marker) => body.includes(marker)).length;
    if (detailHits >= 1) return true;

    const role = this.extractExternalRole();
    return Boolean(role) && !this.isMarketingRoleTitle(role) && body.length >= 200;
  },

  assessExternalJobPayload(payload = {}) {
    const role = payload.role || "";
    const jobText = payload.job_text || "";
    const url = payload.url || location.href;

    if (this.isMarketingRoleTitle(role)) {
      return {
        ok: false,
        message:
          "This looks like a careers landing page, not a specific job. Open the vacancy (e.g. QA Manual Engineer) and analyze again.",
      };
    }

    if (this.isCareersHubPage(jobText) || (!jobText && /\/careers\b/.test(url))) {
      return {
        ok: false,
        message:
          "Careers hub detected. Click into a specific job posting before Analyze.",
      };
    }

    if ((jobText || "").length < 200) {
      return {
        ok: false,
        message:
          "Job description is too short. Open the full vacancy page before Analyze.",
      };
    }

    if (!this.isVacancyDetailPage(jobText)) {
      return {
        ok: false,
        message:
          "Page does not look like a job description. Open the specific vacancy page first.",
      };
    }

    return { ok: true, message: "" };
  },

  normalizeExternalCompany(name) {
    return String(name || "")
      .replace(/\s+careers$/i, "")
      .replace(/\s+jobs$/i, "")
      .trim();
  },

  _findJobPostingNode(node) {
    if (!node || typeof node !== "object") return null;
    const nodeType = node["@type"];
    if (nodeType === "JobPosting" || (Array.isArray(nodeType) && nodeType.includes("JobPosting"))) {
      return node;
    }
    if (Array.isArray(node["@graph"])) {
      for (const item of node["@graph"]) {
        const found = this._findJobPostingNode(item);
        if (found) return found;
      }
    }
    return null;
  },

  extractJsonLdJobPosting() {
    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (const script of scripts) {
      try {
        const parsed = JSON.parse(script.textContent || "null");
        const nodes = Array.isArray(parsed) ? parsed : [parsed];
        for (const node of nodes) {
          const posting = this._findJobPostingNode(node);
          if (posting) return posting;
        }
      } catch (_error) {
        // ignore invalid JSON-LD blocks
      }
    }
    return null;
  },

  extractExternalRole() {
    const jsonLd = this.extractJsonLdJobPosting();
    if (jsonLd?.title) return String(jsonLd.title).trim();

    const fromSelectors = this.textFromSelectors([
      "[data-automation='job-title']",
      "[data-qa='job-title']",
      ".job-title",
      ".posting-headline",
      ".posting-title",
      ".app-title",
      "[class*='job-title']",
      "[class*='JobTitle']",
      "[class*='posting-title']",
      "h1",
    ]);

    if (fromSelectors && !this.isMarketingRoleTitle(fromSelectors)) {
      return fromSelectors;
    }

    return "";
  },

  extractExternalCompany() {
    const jsonLd = this.extractJsonLdJobPosting();
    const org = jsonLd?.hiringOrganization;
    if (typeof org === "string" && org.trim()) {
      return this.normalizeExternalCompany(org.trim());
    }
    if (org?.name) return this.normalizeExternalCompany(String(org.name).trim());

    const ogSite = document.querySelector('meta[property="og:site_name"]')?.content?.trim();
    if (ogSite) return ogSite;

    const fromSelectors = this.textFromSelectors([
      "[data-company-name]",
      "[data-automation='company-name']",
      ".company-name",
      ".posting-company",
      "[class*='company-name']",
      "[class*='CompanyName']",
    ]);
    if (fromSelectors) return this.normalizeExternalCompany(fromSelectors);

    const title = document.title || "";
    const parts = title.split(/[|\-–—]/).map((part) => part.trim()).filter(Boolean);
    if (parts.length >= 2) {
      const last = parts[parts.length - 1];
      if (/career|jobs|hiring|recruit|work/i.test(last)) {
        return this.normalizeExternalCompany(parts[parts.length - 2] || "");
      }
      return this.normalizeExternalCompany(last);
    }

    return "";
  },

  extractExternalJob(fallback = {}) {
    const role = this.extractExternalRole();
    const company = this.extractExternalCompany();
    const jobText = this.collectJobText();
    let pageKind = "unknown";
    if (this.isApplicationLikePage()) {
      pageKind = "application_form";
    } else if (this.isVacancyDetailPage(jobText)) {
      pageKind = "job";
    } else if (this.isCareersHubPage(jobText)) {
      pageKind = "careers_hub";
    }

    return {
      platform: fallback.platform || "external_ats",
      url: location.href,
      title: role || fallback.title || document.title,
      company: company || fallback.company || "",
      role: role || fallback.role || "",
      job_text: this.formatJobTextForAnalysis({
        role: role || fallback.role || "",
        company: company || fallback.company || "",
        job_text: jobText || fallback.job_text || "",
      }),
      page_kind: pageKind,
    };
  },

  isExtensionElement(element) {
    return Boolean(element?.closest("#hr-agent-panel"));
  },

  normalizeFieldLabel(text) {
    return String(text || "")
      .trim()
      .toLowerCase()
      .replace(/\*+/g, "")
      .replace(/\s+/g, " ")
      .trim();
  },

  isGenericFieldLabel(text) {
    const normalized = this.normalizeFieldLabel(text);
    return [
      "single select",
      "select one",
      "choose one",
      "choose an option",
      "select",
      "unknown field",
    ].includes(normalized);
  },

  labelFromFieldName(name) {
    if (!name) return "";
    const key = String(name)
      .toLowerCase()
      .replace(/^job_application\[|\]$/g, "")
      .split(/[.[\]]/)
      .filter(Boolean)
      .pop();

    const known = {
      first_name: "First Name",
      last_name: "Last Name",
      preferred_name: "Preferred First Name",
      preferred_first_name: "Preferred First Name",
      email: "Email",
      phone: "Phone",
      country: "Country",
      linkedin_profile: "LinkedIn Profile",
      linkedin_url: "LinkedIn URL",
      linkedin: "LinkedIn",
      website: "Website",
      cover_letter: "Cover Letter",
      resume: "Resume",
      cv: "Resume/CV",
    };

    if (known[key]) return known[key];
    return key.replace(/_/g, " ").trim();
  },

  resolveFieldLabel(element, label) {
    const resolved = String(label || "").trim();
    if (!this.isGenericFieldLabel(resolved)) return resolved;

    const question = this.findQuestionText(element);
    if (question && !this.isGenericFieldLabel(question) && !this.isPlaceholderLabel(question)) {
      return question;
    }

    const fromName = this.labelFromFieldName(element.name || element.id);
    if (fromName && !this.isGenericFieldLabel(fromName)) return fromName;

    return resolved;
  },

  getAccessibleDocuments() {
    const docs = [document];
    document.querySelectorAll("iframe").forEach((iframe) => {
      try {
        const doc = iframe.contentDocument;
        if (doc && !docs.includes(doc)) docs.push(doc);
      } catch (_error) {
        // Cross-origin iframe — handled by all_frames content scripts.
      }
    });
    return docs;
  },

  isKnownFieldLabel(text) {
    const normalized = this.normalizeFieldLabel(text);
    if (!normalized) return false;

    const known = [
      "email",
      "email address",
      "phone",
      "phone number",
      "mobile",
      "first name",
      "last name",
      "preferred first name",
      "legal first name",
      "legal last name",
      "full name",
      "country",
      "city",
      "location",
      "linkedin",
      "linkedin url",
      "linkedin profile",
      "telegram",
      "telegram username",
      "website",
      "resume",
      "cv",
      "имя",
      "фамилия",
      "телефон",
      "почта",
      "e-mail",
    ];

    return known.some(
      (label) => normalized === label || normalized.startsWith(`${label} `)
    );
  },

  isPlaceholderLabel(text) {
    if (!text) return true;
    const normalized = this.normalizeFieldLabel(text);
    const placeholders = [
      "писать тут",
      "write here",
      "your answer",
      "введите ответ",
      "enter your answer",
      "unknown field",
      "сгенерировать",
      "application status",
      "language",
      "output",
      "notes about this vacancy",
    ];
    if (placeholders.includes(normalized)) return true;
    if (this.isKnownFieldLabel(text)) return false;
    return normalized.length < 12;
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
    if (!element || this.isExtensionElement(element)) return "";

    const doc = element.ownerDocument || document;
    const aria = element.getAttribute("aria-label");
    if (aria && !aria.startsWith("task_")) {
      const resolved = this.resolveFieldLabel(element, aria);
      if (resolved && !this.isPlaceholderLabel(resolved)) {
        return resolved.trim();
      }
    }

    const labelledBy = element.getAttribute("aria-labelledby");
    if (labelledBy) {
      const labelText = labelledBy
        .split(" ")
        .map((id) => doc.getElementById(id)?.innerText?.trim())
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
      if (this.isExtensionElement(element)) return;
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

  extractFormFieldsInAllDocuments() {
    const fields = [];
    const seen = new Set();

    for (const doc of this.getAccessibleDocuments()) {
      for (const field of this.extractFormFieldsFromDocument(doc)) {
        if (seen.has(field.id)) continue;
        seen.add(field.id);
        fields.push(field);
      }
    }

    return fields.slice(0, 40);
  },

  extractFormFieldsFromDocument(rootDoc = document) {
    const fields = [];
    const seen = new Set();

    const addField = (element, label) => {
      if (!element || element.disabled || element.type === "hidden") return;
      if (this.isExtensionElement(element)) return;

      const resolvedLabel = this.resolveFieldLabel(element, label);
      if (!resolvedLabel || this.isPlaceholderLabel(resolvedLabel)) return;

      const id =
        element.id ||
        element.name ||
        `field-${fields.length + 1}-${resolvedLabel.slice(0, 20).replace(/\s+/g, "-")}`;

      if (seen.has(id)) return;
      seen.add(id);

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

    rootDoc
      .querySelectorAll(
        "#application_form .field, form#application_form .field, .application--form .field, .application-form .field, .question"
      )
      .forEach((container) => {
        const input = container.querySelector(
          "input:not([type='hidden']), textarea, select"
        );
        if (!input) return;
        const labelNode = container.querySelector("label, legend, .label, h3, h4, p");
        const label = labelNode?.innerText?.trim() || this.findQuestionText(input);
        addField(input, label);
      });

    rootDoc.querySelectorAll("label").forEach((label) => {
      if (this.isExtensionElement(label)) return;

      const text = label.innerText.trim().replace(/\s+/g, " ");
      const htmlFor = label.getAttribute("for");
      if (!text) return;

      if (htmlFor) {
        const linked = rootDoc.getElementById(htmlFor);
        addField(linked, text);
        return;
      }

      const nested = label.querySelector("input, textarea, select");
      addField(nested, text);
    });

    rootDoc.querySelectorAll("input, textarea, select").forEach((element) => {
      const aria = element.getAttribute("aria-label");
      const question = this.findQuestionText(element);
      const label = this.resolveFieldLabel(element, question || aria || element.name || element.id);
      if (this.isPlaceholderLabel(label)) return;
      addField(element, label);
    });

    return fields;
  },

  extractFormFields() {
    return this.extractFormFieldsInAllDocuments();
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

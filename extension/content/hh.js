(function () {
  const PLATFORM = "hh";

  function extractHhJob() {
    const role = HrAgentExtractors.textFromSelectors([
      "[data-qa='vacancy-title']",
      "h1.vacancy-title",
      "h1",
    ]);
    const company = HrAgentExtractors.textFromSelectors([
      "[data-qa='vacancy-company-name']",
      ".vacancy-company-name",
      "[data-qa='vacancy-company-name'] span",
    ]);
    const jobText = HrAgentExtractors.collectJobText(PLATFORM);
    const pageKind = HrAgentExtractors.isApplicationLikePage()
      ? "application_form"
      : "job";

    return {
      platform: PLATFORM,
      url: location.href,
      title: role,
      company,
      role,
      job_text: jobText,
      page_kind: pageKind,
    };
  }

  function init() {
    const payload = extractHhJob();
    HrAgentPanel.open();
    HrAgentPanel.bindActions(HrAgentActions.bindContentHandlers(payload));
    HrAgentActions.initPanel(payload);
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === "TOGGLE_PANEL") {
      HrAgentPanel.toggle();
    }
  });

  init();
})();

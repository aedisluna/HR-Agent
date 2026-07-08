(function () {
  const PLATFORM = "external_ats";
  const ATS_HOST_HINTS = [
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workday.com",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "breezy.hr",
    "workable.com",
    "icims.com",
    "taleo.net",
    "bamboohr.com",
    "jobvite.com",
    "recruitee.com",
    "personio.de",
    "teamtailor.com",
  ];

  function detectPlatformName() {
    const host = location.hostname.toLowerCase();
    const hint = ATS_HOST_HINTS.find((item) => host.includes(item));
    return hint ? `ats:${hint}` : PLATFORM;
  }

  async function resolveJobContext() {
    const stored = await HrAgentApi.getJobContext();
    if (stored?.job_text) {
      return { ...stored, platform: detectPlatformName() };
    }

    const pageText = HrAgentExtractors.collectJobText();
    return {
      platform: detectPlatformName(),
      url: location.href,
      title: document.title,
      company: stored?.company || "",
      role: stored?.role || document.title,
      job_text: pageText,
      page_kind: "application_form",
    };
  }

  async function init() {
    const looksLikeApplication = HrAgentExtractors.isApplicationLikePage();
    const stored = await HrAgentApi.getJobContext();
    if (!looksLikeApplication && !stored) {
      return;
    }

    const payload = await resolveJobContext();
    HrAgentPanel.ensure();
    HrAgentPanel.bindActions(HrAgentActions.bindContentHandlers(payload));
    HrAgentActions.initPanel(payload);

    if (stored) {
      HrAgentPanel.setStatus(
        "Linked job context loaded. Use Fill form for external application."
      );
    }
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === "TOGGLE_PANEL") {
      HrAgentPanel.toggle();
    }
  });

  init();
})();

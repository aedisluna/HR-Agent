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

  let bootstrapped = false;

  HrAgentFrames.registerFrameListener();

  function detectPlatformName() {
    const host = location.hostname.toLowerCase();
    const hint = ATS_HOST_HINTS.find((item) => host.includes(item));
    return hint ? `ats:${hint}` : PLATFORM;
  }

  async function resolveJobContext() {
    const stored = await HrAgentApi.getJobContext();
    const platform = detectPlatformName();

    if (stored?.job_text) {
      return { ...stored, platform };
    }

    return HrAgentExtractors.extractExternalJob({ platform });
  }

  function shouldActivate(stored) {
    return (
      HrAgentExtractors.isApplicationLikePage() ||
      HrAgentExtractors.isJobLikePage() ||
      Boolean(stored?.job_text)
    );
  }

  async function bootstrap(force = false) {
    if (!HrAgentFrames.isTop()) return;
    if (bootstrapped && !force) return;

    const payload = await resolveJobContext();
    HrAgentPanel.ensure();
    HrAgentPanel.bindActions(HrAgentActions.bindContentHandlers(payload));
    HrAgentActions.initPanel(payload);
    bootstrapped = true;

    const stored = await HrAgentApi.getJobContext();
    if (stored?.job_text) {
      HrAgentPanel.setStatus(
        "Linked job context loaded. Use Fill form for external application."
      );
      return;
    }

    if (payload.role || payload.job_text) {
      HrAgentPanel.setStatus("Vacancy detected on this page.", "success");
      HrAgentLogger.info("External job detected", {
        role: payload.role,
        company: payload.company,
        job_text_chars: payload.job_text?.length || 0,
        page_kind: payload.page_kind,
      });
      return;
    }

    HrAgentPanel.setStatus(
      "Could not detect vacancy details. Use Analyze anyway or open from LinkedIn first."
    );
    HrAgentLogger.warn("External extraction empty", { url: payload.url });
  }

  async function init() {
    if (!HrAgentFrames.isTop()) return;

    const stored = await HrAgentApi.getJobContext();
    if (!shouldActivate(stored)) {
      return;
    }
    await bootstrap();
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === "TOGGLE_PANEL") {
      if (!HrAgentFrames.isTop()) return;

      const panel = document.getElementById("hr-agent-panel");
      const wasHidden = !panel || panel.classList.contains("hidden");
      HrAgentPanel.toggle();
      if (wasHidden) {
        bootstrap(true).catch((error) => {
          HrAgentLogger.error("Panel bootstrap failed", { error: error.message });
        });
      }
    }
  });

  init();
})();

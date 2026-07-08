(function () {

  const PLATFORM = "linkedin";

  let refreshTimer = null;

  let lastSignature = "";



  function extractLinkedInJob() {

    return HrAgentExtractors.extractLinkedInJob({ platform: PLATFORM });

  }



  function jobSignature(payload) {

    return [payload.url, payload.role, payload.company, payload.job_text?.length || 0].join("|");

  }



  function refreshJobContext(force = false) {

    const payload = extractLinkedInJob();

    const signature = jobSignature(payload);

    if (!force && signature === lastSignature) return payload;



    lastSignature = signature;

    HrAgentPanel.bindActions(HrAgentActions.bindContentHandlers(payload));

    HrAgentActions.initPanel(payload);



    if (!payload.role && !payload.job_text) {

      HrAgentLogger.warn("LinkedIn extraction empty", {

        url: payload.url,

        page_kind: payload.page_kind,

      });

    } else {

      HrAgentLogger.info("LinkedIn job refreshed", {

        role: payload.role,

        company: payload.company,

        job_text_chars: payload.job_text?.length || 0,

      });

    }



    return payload;

  }



  function scheduleRefresh() {

    clearTimeout(refreshTimer);

    refreshTimer = setTimeout(() => refreshJobContext(), 350);

  }



  function init() {

    refreshJobContext(true);

    HrAgentPanel.open();



    window.addEventListener("popstate", scheduleRefresh);

    window.addEventListener("hashchange", scheduleRefresh);



    const urlObserver = new MutationObserver(() => {

      if (location.href !== urlObserver._lastUrl) {

        urlObserver._lastUrl = location.href;

        scheduleRefresh();

      }

    });

    urlObserver._lastUrl = location.href;

    urlObserver.observe(document.querySelector("title") || document.head, {

      childList: true,

      subtree: true,

      characterData: true,

    });



    const domObserver = new MutationObserver(scheduleRefresh);

    domObserver.observe(document.body, { childList: true, subtree: true });



    document.addEventListener(

      "click",

      (event) => {

        const target = event.target;

        if (!(target instanceof HTMLElement)) return;



        const jobCard = target.closest(

          ".job-card-container, .jobs-search-results__list-item, [data-job-id], a[href*='/jobs/view/']"

        );

        if (jobCard) {

          scheduleRefresh();

        }



        const applyButton = target.closest(

          "button,jobs-apply-button,.jobs-apply-button"

        );

        if (!applyButton) return;

        const text = applyButton.textContent?.toLowerCase() || "";

        if (text.includes("apply") || text.includes("easy apply")) {

          HrAgentApi.saveJobContext(extractLinkedInJob());

        }

      },

      true

    );

  }



  chrome.runtime.onMessage.addListener((message) => {

    if (message.type === "TOGGLE_PANEL") {

      const panel = document.getElementById("hr-agent-panel");

      const wasHidden = !panel || panel.classList.contains("hidden");

      HrAgentPanel.toggle();

      if (wasHidden) {

        refreshJobContext(true);

      }

    }

  });



  init();

})();


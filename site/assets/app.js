(function () {
  const searchInput = document.getElementById("search-input");
  const githubOnly = document.getElementById("github-only");
  const tierFilter = document.getElementById("tier-filter");
  const sortSelect = document.getElementById("sort-select");
  const resultCount = document.getElementById("result-count");
  const localClickCount = document.getElementById("local-click-count");
  const localFeedbackCount = document.getElementById("local-feedback-count");
  const exportFeedbackBtn = document.getElementById("export-feedback");
  const cardGrid = document.getElementById("card-grid");
  const cards = Array.from(document.querySelectorAll(".news-card"));
  if (!cardGrid || !cards.length) return;

  const CLICK_KEY = "anm_click_events";
  const FEEDBACK_KEY = "anm_feedback_events";

  function getScore(card) {
    const raw = card.getAttribute("data-score") || "0";
    const num = Number(raw);
    return Number.isFinite(num) ? num : 0;
  }

  function applyFilters() {
    const q = (searchInput?.value || "").toLowerCase().trim();
    const onlyGithub = !!githubOnly?.checked;
    const tier = tierFilter?.value || "all";
    let visible = 0;

    cards.forEach((card) => {
      const text = (card.textContent || "").toLowerCase();
      const isGithub = card.dataset.hasGithub === "true";
      const currentTier = card.dataset.tier || "primary";
      const matchQ = !q || text.includes(q);
      const matchGithub = !onlyGithub || isGithub;
      const matchTier = tier === "all" || currentTier === tier;
      const show = matchQ && matchGithub && matchTier;
      card.style.display = show ? "" : "none";
      if (show) visible += 1;
    });

    if (resultCount) resultCount.textContent = String(visible);
  }

  function applySort() {
    const mode = sortSelect?.value || "score_desc";
    const sorted = cards.slice().sort((a, b) => {
      const sa = getScore(a);
      const sb = getScore(b);
      if (mode === "score_asc") return sa - sb;
      return sb - sa;
    });
    sorted.forEach((card) => cardGrid.appendChild(card));
  }

  function readEvents(key) {
    try {
      return JSON.parse(localStorage.getItem(key) || "[]");
    } catch (_) {
      return [];
    }
  }

  function appendEvent(key, payload) {
    const previous = readEvents(key);
    previous.push(payload);
    localStorage.setItem(key, JSON.stringify(previous.slice(-500)));
  }

  function trackClick(linkEl) {
    const card = linkEl.closest(".news-card, .focus-card");
    if (!card) return;
    const payload = {
      ts: new Date().toISOString(),
      item_id: card.dataset.itemId || "",
      title: card.dataset.title || "",
      source: card.dataset.source || "",
      href: card.dataset.link || linkEl.href || "",
      label: "open",
      channel: "web",
    };
    appendEvent(CLICK_KEY, payload);
    renderLocalCounts();

    if (typeof window.plausible === "function") {
      window.plausible("open_link", {
        props: { source: payload.source || "unknown" },
      });
    }
  }

  function trackFeedback(btnEl) {
    const card = btnEl.closest(".news-card, .focus-card");
    if (!card) return;
    const label = btnEl.dataset.feedback || "";
    if (!label) return;
    const payload = {
      ts: new Date().toISOString(),
      item_id: card.dataset.itemId || "",
      title: card.dataset.title || "",
      source: card.dataset.source || "",
      href: card.dataset.link || "",
      label,
      channel: "web",
    };
    appendEvent(FEEDBACK_KEY, payload);
    renderLocalCounts();

    if (typeof window.plausible === "function") {
      window.plausible("feedback", {
        props: { label, source: payload.source || "unknown" },
      });
    }
  }

  function downloadFeedback() {
    const events = readEvents(FEEDBACK_KEY);
    const blob = new Blob([JSON.stringify(events, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "anm_feedback_export.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  function renderLocalCounts() {
    const today = new Date().toISOString().slice(0, 10);
    if (localClickCount) {
      const clicks = readEvents(CLICK_KEY).filter((x) => String(x.ts || "").startsWith(today)).length;
      localClickCount.textContent = String(clicks);
    }
    if (localFeedbackCount) {
      localFeedbackCount.textContent = String(readEvents(FEEDBACK_KEY).length);
    }
  }

  function update() {
    applySort();
    applyFilters();
  }

  searchInput?.addEventListener("input", update);
  githubOnly?.addEventListener("change", update);
  tierFilter?.addEventListener("change", update);
  sortSelect?.addEventListener("change", update);
  document.querySelectorAll(".news-card a, .focus-card a").forEach((a) => {
    a.addEventListener("click", () => trackClick(a));
  });
  document.querySelectorAll(".feedback-btn").forEach((btn) => {
    btn.addEventListener("click", () => trackFeedback(btn));
  });
  exportFeedbackBtn?.addEventListener("click", downloadFeedback);

  renderLocalCounts();
  update();
})();


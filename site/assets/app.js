(function () {
  const searchInput = document.getElementById("search-input");
  const githubOnly = document.getElementById("github-only");
  const tierFilter = document.getElementById("tier-filter");
  const sortSelect = document.getElementById("sort-select");
  const resultCount = document.getElementById("result-count");
  const localClickCount = document.getElementById("local-click-count");
  const cardGrid = document.getElementById("card-grid");
  const cards = Array.from(document.querySelectorAll(".news-card"));
  if (!cardGrid || !cards.length) return;

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

  function update() {
    applySort();
    applyFilters();
  }

  function trackClick(linkEl) {
    const card = linkEl.closest(".news-card, .focus-card");
    if (!card) return;
    const sourceText = (card.querySelector(".meta span")?.textContent || "").replace("Source:", "").trim();
    const title = (card.querySelector("h2, h3")?.textContent || "").trim();
    const payload = {
      ts: new Date().toISOString(),
      title,
      source: sourceText,
      href: linkEl.href || "",
    };
    try {
      const key = "anm_click_events";
      const previous = JSON.parse(localStorage.getItem(key) || "[]");
      previous.push(payload);
      const trimmed = previous.slice(-200);
      localStorage.setItem(key, JSON.stringify(trimmed));
      renderLocalClickCount();
    } catch (_) {}

    if (typeof window.plausible === "function") {
      window.plausible("open_link", {
        props: { source: sourceText || "unknown" },
      });
    }
  }

  function renderLocalClickCount() {
    if (!localClickCount) return;
    const today = new Date().toISOString().slice(0, 10);
    try {
      const key = "anm_click_events";
      const events = JSON.parse(localStorage.getItem(key) || "[]");
      const count = events.filter((x) => String(x.ts || "").startsWith(today)).length;
      localClickCount.textContent = String(count);
    } catch (_) {
      localClickCount.textContent = "0";
    }
  }

  searchInput?.addEventListener("input", update);
  githubOnly?.addEventListener("change", update);
  tierFilter?.addEventListener("change", update);
  sortSelect?.addEventListener("change", update);
  document.querySelectorAll(".news-card a, .focus-card a").forEach((a) => {
    a.addEventListener("click", () => trackClick(a));
  });
  renderLocalClickCount();
  update();
})();

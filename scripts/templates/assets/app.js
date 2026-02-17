(function () {
  const searchInput = document.getElementById("search-input");
  const githubOnly = document.getElementById("github-only");
  const resultCount = document.getElementById("result-count");
  const cards = Array.from(document.querySelectorAll(".news-card"));
  if (!cards.length) return;

  function applyFilters() {
    const q = (searchInput?.value || "").toLowerCase().trim();
    const onlyGithub = !!githubOnly?.checked;
    let visible = 0;
    cards.forEach((card) => {
      const text = (card.textContent || "").toLowerCase();
      const isGithub = card.dataset.hasGithub === "true";
      const matchQ = !q || text.includes(q);
      const matchGithub = !onlyGithub || isGithub;
      const show = matchQ && matchGithub;
      card.style.display = show ? "" : "none";
      if (show) visible += 1;
    });
    if (resultCount) resultCount.textContent = String(visible);
  }

  searchInput?.addEventListener("input", applyFilters);
  githubOnly?.addEventListener("change", applyFilters);
})();

(function () {
  const config = window.FYME_CONFIG || {};
  const apiBaseUrl = String(config.apiBaseUrl || "").trim().replace(/\/+$/, "");
  const cacheKey = "forYouAndMeEscape.remoteStateCache";
  const requestTimeoutMs = 5000;

  function normalizeState(state) {
    const solvedStages = state && typeof state.solvedStages === "object" ? state.solvedStages : {};
    const availableStages = state && typeof state.availableStages === "object" ? state.availableStages : {};
    const serverTime = typeof state?.serverTime === "string" ? state.serverTime : "";

    return {
      solvedStages,
      availableStages,
      serverTime
    };
  }

  function readCache() {
    try {
      const raw = localStorage.getItem(cacheKey);
      if (!raw) {
        return null;
      }

      return normalizeState(JSON.parse(raw));
    } catch (error) {
      return null;
    }
  }

  function writeCache(state) {
    try {
      localStorage.setItem(cacheKey, JSON.stringify(normalizeState(state)));
    } catch (error) {
      // Cache writes are best-effort.
    }
  }

  function buildUrl(path) {
    const suffix = String(path || "").startsWith("/") ? path : `/${path}`;
    return `${apiBaseUrl}${suffix}`;
  }

  async function requestJson(path, options = {}) {
    if (!apiBaseUrl) {
      throw new Error("Backend not configured");
    }

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), requestTimeoutMs);

    try {
      const response = await fetch(buildUrl(path), {
        ...options,
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          ...(options.headers || {})
        },
        signal: controller.signal
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = payload?.message || payload?.error || `Request failed with status ${response.status}`;
        throw new Error(message);
      }

      return normalizeState(payload);
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  async function fetchState() {
    const state = await requestJson("/state", { method: "GET" });
    writeCache(state);
    return state;
  }

  async function solveStage(stageId) {
    const state = await requestJson("/solve", {
      method: "POST",
      body: JSON.stringify({ stageId })
    });
    writeCache(state);
    return state;
  }

  async function unlockStage(stageId, token) {
    const state = await requestJson("/admin/unlock", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ stageId })
    });
    writeCache(state);
    return state;
  }

  window.FYME_REMOTE = {
    enabled: Boolean(apiBaseUrl),
    apiBaseUrl,
    fetchState,
    solveStage,
    unlockStage,
    getCachedState: readCache,
    cacheState: writeCache,
    normalizeState
  };
})();

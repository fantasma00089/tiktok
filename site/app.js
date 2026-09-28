// Site estático (Netlify): consulta o status do monitor e exibe o aviso de repost.
//
// Fontes, em ordem de preferência:
//   1. Tunnel  -> {TUNNEL_URL}/status   (backend local exposto por ngrok/Cloudflare)
//   2. Webhook -> ./status.json          (publicado pelo monitor via API da Netlify)
// Para testar outra URL sem editar o config.js: ?api=https://abc.ngrok-free.app
(() => {
  "use strict";

  const cfg = Object.assign(
    { TUNNEL_URL: "", POLL_INTERVAL_MS: 30000, REQUEST_TIMEOUT_MS: 8000 },
    window.REPOST_CONFIG || {}
  );
  const $ = (id) => document.getElementById(id);
  const SEEN_KEY = "repost-alert:last-seen-id";
  let currentAlertId = null;

  const store = {
    get(key) { try { return localStorage.getItem(key); } catch (_) { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (_) { /* modo privado */ } },
  };

  function tunnelBase() {
    const fromQuery = new URLSearchParams(location.search).get("api");
    return (fromQuery || cfg.TUNNEL_URL || "").replace(/\/+$/, "");
  }

  function sources() {
    const list = [];
    const base = tunnelBase();
    if (base) list.push({ name: "tunnel", url: `${base}/status`, live: true });
    list.push({ name: "status.json", url: `status.json?t=${Date.now()}`, live: false });
    return list;
  }

  async function fetchJson(url) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), cfg.REQUEST_TIMEOUT_MS);
    try {
      const res = await fetch(url, {
        cache: "no-store",
        signal: ctrl.signal,
        // Evita a página de aviso do ngrok (plano gratuito) em requisições fetch.
        headers: { "ngrok-skip-browser-warning": "1" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } finally {
      clearTimeout(timer);
    }
  }

  async function loadStatus() {
    let lastError;
    for (const src of sources()) {
      try {
        return { data: await fetchJson(src.url), src };
      } catch (err) {
        lastError = err;
      }
    }
    throw lastError;
  }

  // O alerta vale enquanto o repost estiver dentro da janela configurada no monitor.
  // Calculado aqui também para que um status.json antigo não fique "em alerta" para sempre.
  function isAlert(data) {
    const latest = data.ultimo_repost;
    if (!latest || !latest.detected_at) return false;
    const windowMin = Number(data.janela_alerta_minutos || 60);
    const ageMin = (Date.now() - new Date(latest.detected_at).getTime()) / 60000;
    return ageMin <= windowMin;
  }

  function relative(iso) {
    if (!iso) return "";
    const min = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (min < 1) return "agora mesmo";
    if (min < 60) return `há ${min} minuto${min === 1 ? "" : "s"}`;
    const h = Math.floor(min / 60);
    if (h < 48) return `há ${h} hora${h === 1 ? "" : "s"}`;
    return `há ${Math.floor(h / 24)} dias`;
  }

  const fmt = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR") : "—");
  const videoTitle = (r) => (r.author ? `Vídeo de @${r.author}` : "Vídeo repostado");

  function render(data, src) {
    const who = data.alvo || (data.username ? `@${data.username}` : "Perfil monitorado");
    $("target").textContent = who;
    const latest = data.ultimo_repost;
    const alert = isAlert(data);
    const offline = src.live ? data.monitor_online === false : false;

    const card = $("card");
    card.className = "card " + (alert ? "state-alert" : offline ? "state-offline" : "state-waiting");
    if (alert) {
      $("headline").textContent = `${who} repostou um vídeo!`;
      $("subline").textContent = `Repost detectado ${relative(latest.detected_at)}.`;
    } else {
      $("headline").textContent = offline ? "Monitor pausado" : "Aguardando repost";
      $("subline").textContent = latest
        ? `Último repost ${relative(latest.detected_at)} (${fmt(latest.detected_at)}).`
        : "Nenhum repost detectado desde o início do monitoramento.";
    }

    $("latest").hidden = !latest;
    if (latest) {
      $("latest-title").textContent = videoTitle(latest);
      $("latest-desc").textContent = latest.description || "";
      $("latest-link").href = latest.url;
      const img = $("latest-cover");
      img.hidden = !latest.cover_url;
      if (latest.cover_url) img.src = latest.cover_url;
    }

    const items = data.reposts_recentes || [];
    $("history-wrap").hidden = items.length < 2;
    const list = $("history");
    list.replaceChildren(...items.map((r) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = r.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = videoTitle(r) + (r.description ? ` — ${r.description.slice(0, 70)}` : "");
      const t = document.createElement("time");
      t.className = "small muted";
      t.dateTime = r.detected_at || "";
      t.textContent = relative(r.detected_at);
      li.append(a, t);
      return li;
    }));

    $("source").textContent = src.live ? "Conectado ao monitor (tempo real)" : "Status publicado";
    $("updated").textContent = `atualizado ${relative(data.gerado_em) || "—"}`;

    currentAlertId = alert ? latest.item_id : null;
    // Banner enquanto estiver na janela de alerta; modal só para um repost ainda não visto.
    $("banner").hidden = !alert || store.get(SEEN_KEY + ":banner") === latest.item_id;
    if (alert) {
      $("banner-text").textContent = `🔴 ${who} acabou de repostar um vídeo (${relative(latest.detected_at)})`;
      $("banner-link").href = latest.url;
      if (store.get(SEEN_KEY) !== latest.item_id) showModal(who, latest);
    }
  }

  function showModal(who, latest) {
    const modal = $("modal");
    $("modal-title").textContent = `${who} repostou um vídeo!`;
    $("modal-desc").textContent = latest.description || videoTitle(latest);
    $("modal-link").href = latest.url;
    modal.dataset.itemId = latest.item_id;
    if (typeof modal.showModal === "function" && !modal.open) modal.showModal();
    if ("Notification" in window && Notification.permission === "granted" && !document.hasFocus()) {
      const n = new Notification(`${who} repostou um vídeo!`, { body: latest.description || latest.url, tag: latest.item_id });
      n.onclick = () => window.open(latest.url, "_blank", "noopener");
    }
  }

  function markSeen() {
    const modal = $("modal");
    if (modal.dataset.itemId) store.set(SEEN_KEY, modal.dataset.itemId);
    if (modal.open) modal.close();
  }

  $("modal-close").addEventListener("click", markSeen);
  $("modal-link").addEventListener("click", markSeen);
  $("modal").addEventListener("cancel", markSeen);
  $("banner-close").addEventListener("click", () => {
    if (currentAlertId) store.set(SEEN_KEY + ":banner", currentAlertId);
    $("banner").hidden = true;
  });

  if ("Notification" in window && Notification.permission === "default") {
    const btn = $("enable-notif");
    btn.hidden = false;
    btn.addEventListener("click", async () => {
      await Notification.requestPermission();
      btn.hidden = true;
    });
  }

  let failures = 0;
  async function tick() {
    try {
      const { data, src } = await loadStatus();
      failures = 0;
      render(data, src);
    } catch (err) {
      failures += 1;
      $("card").className = "card state-offline";
      $("headline").textContent = "Não foi possível obter o status";
      $("subline").textContent = "O monitor pode estar desligado. Tentando novamente…";
      $("source").textContent = `Erro: ${err.message || err}`;
    }
    // Backoff simples se o monitor estiver fora do ar (máx. 5 min).
    const delay = Math.min(cfg.POLL_INTERVAL_MS * 2 ** Math.min(failures, 4), 300000);
    setTimeout(tick, delay);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") loadStatus().then(({ data, src }) => render(data, src)).catch(() => {});
  });

  tick();
})();

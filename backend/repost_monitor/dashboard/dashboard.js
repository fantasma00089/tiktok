// Painel local: recebe o status em tempo real via Server-Sent Events (/api/events)
// e cai para polling de /api/state se a conexão SSE não estiver disponível.
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const BASE_TITLE = document.title;
  let current = null;
  let lastAlertedId = null;

  const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR") : "—");

  function relative(iso) {
    if (!iso) return "";
    const minutes = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (minutes < 1) return "agora mesmo";
    if (minutes < 60) return `há ${minutes} minuto${minutes === 1 ? "" : "s"}`;
    const hours = Math.floor(minutes / 60);
    if (hours < 48) return `há ${hours} hora${hours === 1 ? "" : "s"}`;
    return `há ${Math.floor(hours / 24)} dias`;
  }

  function countdown(iso) {
    if (!iso) return "—";
    const s = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
    if (s <= 0) return "em instantes";
    return s < 60 ? `em ${s}s` : `em ${Math.floor(s / 60)}min ${s % 60}s`;
  }

  // Partes que dependem do relógio: atualizadas a cada segundo sem recriar o DOM.
  function renderTimes() {
    const s = current;
    if (!s) return;
    const latest = s.ultimo_repost;
    const alert = Boolean(latest && s.repostou);
    $("status-text").textContent = alert ? `Repost detectado ${relative(latest.detected_at)}` : s.mensagem;
    $("status-sub").textContent = alert
      ? `${s.alvo} repostou um vídeo.`
      : latest
        ? `Último repost ${relative(latest.detected_at)} (${fmtTime(latest.detected_at)}).`
        : `Monitorando ${s.alvo} a cada ~${Math.round(s.intervalo_polling_segundos / 60)} min.`;
    if (latest) $("latest-time").textContent = `Detectado ${relative(latest.detected_at)} · ${fmtTime(latest.detected_at)}`;
    $("next-check").textContent = countdown(s.proxima_verificacao);
  }

  function render() {
    const s = current;
    if (!s) return;
    $("target").textContent = s.alvo || "—";
    $("sim-warning").hidden = !s.modo_simulacao;

    const card = $("status-card");
    const latest = s.ultimo_repost;
    const alert = Boolean(latest && s.repostou);
    card.className = "card status " + ({
      repost_detectado: "status-alert",
      erro: "status-error",
      iniciando: "status-starting",
    }[s.status] || "status-idle");
    document.title = alert ? `🔴 Repost! · ${BASE_TITLE}` : BASE_TITLE;
    renderTimes();

    $("latest").hidden = !latest;
    if (latest) {
      $("latest-author").textContent = latest.author ? `Vídeo de @${latest.author}` : "Vídeo repostado";
      $("latest-desc").textContent = latest.description || "";
      $("latest-link").href = latest.url;
      const cover = $("latest-cover");
      cover.hidden = !latest.cover_url;
      if (latest.cover_url) cover.src = latest.cover_url;
    }

    $("last-check").textContent = fmtTime(s.ultima_verificacao);
    if (s.provedor) $("provider").textContent = s.provedor;
    if (s.total_verificacoes != null) $("checks").textContent = s.total_verificacoes;
    if ("netlify" in s) $("netlify").textContent = s.netlify || "não configurado";
    $("failures").textContent = s.falhas_consecutivas || 0;
    $("error").hidden = !s.erro;
    $("error").textContent = s.erro ? `Último erro: ${s.erro}` : "";

    const list = $("history");
    list.replaceChildren();
    const items = s.reposts_recentes || [];
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "Nenhum repost detectado ainda.";
      list.append(li);
    }
    for (const r of items) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = r.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = r.author ? `@${r.author}` : r.item_id;
      if (r.description) a.textContent += ` — ${r.description.slice(0, 80)}`;
      const time = document.createElement("span");
      time.className = "small muted";
      time.textContent = `${fmtTime(r.detected_at)} (${relative(r.detected_at)})`;
      li.append(a, time);
      list.append(li);
    }

    if (alert && latest.item_id !== lastAlertedId) {
      if (lastAlertedId !== null) browserAlert(s, latest);
      lastAlertedId = latest.item_id;
    } else if (lastAlertedId === null && latest) {
      lastAlertedId = latest.item_id;
    }
  }

  function browserAlert(s, latest) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    const n = new Notification(`${s.alvo} repostou um vídeo!`, {
      body: latest.description || latest.url,
      tag: latest.item_id,
    });
    n.onclick = () => window.open(latest.url, "_blank", "noopener");
  }

  async function refresh() {
    try {
      const res = await fetch("/api/state", { cache: "no-store" });
      if (res.ok) {
        current = await res.json();
        render();
      }
    } catch (_) { /* servidor fora do ar; tenta de novo no próximo ciclo */ }
  }

  function connect() {
    if (!("EventSource" in window)) {
      setInterval(refresh, 10000);
      return;
    }
    const es = new EventSource("/api/events");
    es.addEventListener("open", () => {
      $("conn").textContent = "ao vivo";
      $("conn").className = "pill pill-on";
      refresh(); // traz campos extras (provedor, netlify) que o SSE não envia
    });
    es.addEventListener("status", (e) => {
      current = { ...current, ...JSON.parse(e.data) };
      render();
    });
    es.addEventListener("repost", () => refresh());
    es.addEventListener("error", () => {
      $("conn").textContent = "reconectando…";
      $("conn").className = "pill pill-off";
    });
  }

  async function action(button, path, okText) {
    button.disabled = true;
    $("action-msg").textContent = "Executando…";
    try {
      const res = await fetch(path, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.ok === false) throw new Error(data.detail || data.erro || `HTTP ${res.status}`);
      $("action-msg").textContent = typeof okText === "function" ? okText(data) : okText;
      await refresh();
    } catch (err) {
      $("action-msg").textContent = `Falhou: ${err.message}`;
    } finally {
      button.disabled = false;
    }
  }

  $("btn-check").addEventListener("click", (e) => action(e.currentTarget, "/api/check-now", (d) =>
    d.novos_reposts && d.novos_reposts.length
      ? `${d.novos_reposts.length} repost(s) novo(s) detectado(s)!`
      : `Verificado: nenhum repost novo (${d.itens_consultados} itens consultados).`));
  $("btn-notify").addEventListener("click", (e) => action(e.currentTarget, "/api/test-notification", "Notificação de teste enviada."));
  $("btn-open").addEventListener("click", (e) => action(e.currentTarget, "/api/open-latest", "Vídeo aberto no navegador."));
  $("btn-browser-notif").addEventListener("click", async () => {
    if (!("Notification" in window)) {
      $("action-msg").textContent = "Este navegador não suporta notificações.";
      return;
    }
    const perm = await Notification.requestPermission();
    $("action-msg").textContent = perm === "granted" ? "Alertas do navegador ativados." : "Permissão negada.";
  });

  setInterval(renderTimes, 1000); // contagem regressiva e tempos relativos
  refresh();
  connect();
})();

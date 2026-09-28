// Configuração do site. Edite antes do deploy na Netlify.
window.REPOST_CONFIG = {
  // Modo tunnel: URL pública do backend local exposta por ngrok / Cloudflare Tunnel
  // (sem barra no final). Ex.: "https://abc123.ngrok-free.app" ou "https://status.seudominio.com".
  // Deixe vazio para usar apenas o modo webhook reverso (status.json publicado pelo monitor).
  TUNNEL_URL: "",

  // Intervalo de consulta do status (ms).
  POLL_INTERVAL_MS: 30000,

  // Tempo máximo de espera por resposta (ms) antes de tentar a próxima fonte.
  REQUEST_TIMEOUT_MS: 8000,
};

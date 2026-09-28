# Tunnel reverso (ngrok / Cloudflare Tunnel)

O site na Netlify precisa alcançar `http://127.0.0.1:8000/status` no seu PC. Um tunnel cria uma
URL HTTPS pública que encaminha para essa porta.

Somente `/status`, `/status.json` e `/health` respondem através do tunnel. O painel e as rotas
`/api/*` retornam **403** para qualquer requisição que chegue com cabeçalhos de proxy
(`X-Forwarded-For`, `Cf-Connecting-Ip`...).

## Cloudflare Tunnel (recomendado, gratuito)

### Rápido (sem conta, URL muda a cada execução)

```bash
./scripts/start-tunnel.sh cloudflare      # Windows: .\scripts\start-tunnel.ps1 cloudflare
```
Copie a URL `https://xxxx.trycloudflare.com` exibida e use-a em `site/config.js` (`TUNNEL_URL`) ou
em `?api=` no endereço do site.

### Nomeado (URL fixa, precisa de um domínio na Cloudflare)

```bash
cloudflared tunnel login
cloudflared tunnel create repost-monitor
cloudflared tunnel route dns repost-monitor status.seudominio.com
```
Copie `tunnel/cloudflared-config.example.yml` para `~/.cloudflared/config.yml`, ajuste
`credentials-file` e `hostname` e rode:
```bash
cloudflared tunnel run repost-monitor
```
O exemplo já filtra por caminho: apenas `/status`, `/status.json` e `/health` são encaminhados.
Para iniciar com o sistema: `cloudflared service install`.

## ngrok

```bash
ngrok config add-authtoken <SEU_TOKEN>
./scripts/start-tunnel.sh ngrok                          # URL aleatória
./scripts/start-tunnel.sh ngrok seu-nome.ngrok-free.app  # domínio estático gratuito
```

O plano gratuito mostra uma página de aviso em navegadores; o `app.js` envia o cabeçalho
`ngrok-skip-browser-warning`, e o backend libera esse cabeçalho no CORS, então o `fetch()` funciona.

## Conferindo

```bash
curl https://SUA-URL/status          # deve retornar o JSON
curl -i https://SUA-URL/api/state    # deve retornar 403
```

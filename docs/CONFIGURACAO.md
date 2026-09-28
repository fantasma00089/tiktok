# Configuração

Toda a configuração fica em `backend/.env` (modelo: `backend/.env.example`). Variáveis de ambiente
do sistema têm prioridade sobre o arquivo. Use `python -m repost_monitor --env-file outro.env <comando>`
para apontar para outro arquivo.

## Alvo

| Variável | Padrão | Descrição |
|---|---|---|
| `TIKTOK_USERNAME` | — | `@` do perfil, com ou sem o `@` |
| `TIKTOK_USER_ID` | — | ID numérico (alguns provedores preferem). Pelo menos um dos dois é obrigatório |

Trocar o alvo reinicia o estado automaticamente (uma nova leitura de base é feita).

## Polling e resiliência

| Variável | Padrão | Descrição |
|---|---|---|
| `POLL_INTERVAL_SECONDS` | `180` | Intervalo entre consultas. Recomendado 120–300. Mínimo aceito: 30 |
| `POLL_JITTER_SECONDS` | `15` | Variação aleatória (±) do intervalo |
| `RETRY_ATTEMPTS` | `3` | Tentativas por requisição (falhas de rede, HTTP 408/425/429/5xx) |
| `RETRY_BASE_DELAY_SECONDS` | `2` | Espera inicial entre tentativas (dobra a cada tentativa; `Retry-After` é respeitado) |
| `MAX_BACKOFF_SECONDS` | `1800` | Teto do intervalo após falhas seguidas (o intervalo dobra a cada ciclo com erro) |
| `HTTP_TIMEOUT_SECONDS` | `30` | Timeout de cada requisição |

Erros 4xx que não são transitórios (401, 403, 404) não são repetidos — geralmente indicam chave ou URL errada.

## Detecção

| Variável | Padrão | Descrição |
|---|---|---|
| `ALERT_WINDOW_MINUTES` | `60` | Por quanto tempo depois da detecção `/status` responde `"repostou": true` |
| `BASELINE_ON_FIRST_RUN` | `true` | Na 1ª leitura, registra os reposts existentes sem alertar |
| `MAX_SEEN_IDS` | `500` | Quantos IDs já vistos guardar |

O estado fica em `backend/data/state.json` (`last_item_id`, `seen_ids`, histórico de detecções).
Cada detecção também é registrada em `backend/logs/reposts.jsonl` (timestamp, `@` monitorado, URL do vídeo).
O log geral fica em `backend/logs/monitor.log` (rotativo, 5 × 2 MB).

## Servidor local

| Variável | Padrão | Descrição |
|---|---|---|
| `HOST` | `127.0.0.1` | Use `0.0.0.0` apenas se o agente em Docker (OpenHands) precisar acessar a API |
| `PORT` | `8000` | Porta do painel e do `/status` |
| `CORS_ORIGINS` | `*` | Origens que podem ler `/status` (ex.: `https://seu-site.netlify.app`) |
| `ADMIN_TOKEN` | — | Libera `/api/*` para quem não está no próprio PC (cabeçalho `Authorization: Bearer <token>` ou `X-Admin-Token`) |

Rotas públicas: `/status`, `/status.json`, `/health`. Todo o resto (painel, `/api/check-now`,
`/api/open-latest`...) só responde a acessos diretos do próprio PC — requisições vindas do tunnel
são identificadas pelos cabeçalhos de proxy e recebem 403.

## Notificações locais

| Variável | Padrão | Descrição |
|---|---|---|
| `DESKTOP_NOTIFICATIONS` | `true` | Toast nativo (Windows via PowerShell/WinRT, macOS via `osascript`, Linux via `notify-send`) |
| `OPEN_BROWSER_ON_REPOST` | `false` | Abre o vídeo automaticamente no navegador padrão |

No Windows, clicar no toast (ou no botão “Abrir vídeo”) abre o vídeo repostado.

## Publicação no site (webhook reverso)

| Variável | Padrão | Descrição |
|---|---|---|
| `NETLIFY_AUTH_TOKEN` | — | Personal access token da Netlify |
| `NETLIFY_SITE_ID` | — | *Site ID* (Site configuration → General) |
| `NETLIFY_SITE_DIR` | `../site` | Pasta do site publicada junto com o `status.json` |
| `NETLIFY_MIN_INTERVAL_SECONDS` | `60` | Intervalo mínimo entre deploys |
| `NETLIFY_HEARTBEAT_MINUTES` | `0` | Se > 0, republica periodicamente mesmo sem repost |
| `WEBHOOK_URL` | — | URL que recebe um POST com o status (JSON) a cada repost novo |
| `WEBHOOK_SECRET` | — | Assina o corpo em `X-Repost-Signature: sha256=<hmac>` |

## Provedores

`PROVIDER` escolhe de onde vêm os dados (padrão: `browser`). Todos devolvem a lista de reposts do mais recente para o mais antigo.

### `browser` — navegador local (padrão, sem API)

A cada ciclo o monitor abre o perfil num navegador invisível, clica na aba **Reposts** e lê a lista
que o próprio site do TikTok carrega (`/api/repost/item_list`); se ela não vier, lê os links de vídeo
da aba. Imagens, vídeos e fontes são bloqueados e o navegador é fechado ao final de cada ciclo.

| Variável | Padrão | Descrição |
|---|---|---|
| `BROWSER_CHANNEL` | `msedge` no Windows, vazio nos outros | Navegador: `msedge`, `chrome` ou vazio (Chromium do Playwright) |
| `BROWSER_HEADLESS` | `true` | `false` mostra a janela durante a verificação (útil para depurar) |
| `BROWSER_TIMEOUT_SECONDS` | `45` | Tempo máximo para carregar o perfil |
| `BROWSER_BLOCK_MEDIA` | `true` | Não carrega imagens, vídeos e fontes |
| `BROWSER_PROFILE_DIR` | `data/browser-profile` | Perfil do navegador (cookies do TikTok) |

Se o TikTok pedir captcha ou login, o painel mostra o erro. Feche o `iniciar.bat`, rode
`abrir-navegador.bat` (ou `python -m repost_monitor abrir-navegador`), resolva na janela, feche-a e
inicie de novo. Os cookies ficam salvos no perfil do navegador.

### `mock` — simulação
**Não consulta o TikTok**: reposts reais nunca aparecem neste modo, e o painel mostra um aviso.
Lê `MOCK_FILE` (padrão `backend/data/mock_reposts.json`). Use `repost_monitor simulate` para inserir um repost.

### `http` — qualquer API REST/JSON (PrimeApi, YepAPI, RapidAPI, tikwm...)

| Variável | Descrição |
|---|---|
| `HTTP_API_URL` | URL com `{username}` e/ou `{user_id}` |
| `HTTP_API_METHOD` | `GET` ou `POST` |
| `HTTP_API_HEADERS` | JSON com cabeçalhos, ex.: `{"x-rapidapi-key": "...", "x-rapidapi-host": "..."}` |
| `HTTP_API_BODY` | JSON do corpo (POST), aceita os mesmos placeholders |
| `HTTP_API_ITEMS_PATH` | Caminho da lista no JSON, ex.: `data.videos`. Vazio = detecção automática |
| `HTTP_API_ID_FIELD`, `HTTP_API_URL_FIELD`, `HTTP_API_AUTHOR_FIELD`, `HTTP_API_DESCRIPTION_FIELD`, `HTTP_API_COVER_FIELD` | Caminhos dos campos em cada item (ex.: `author.unique_id`, `video.cover`). Vazio = nomes mais comuns |

Exemplo (endpoint hipotético — use o que a documentação do seu provedor indicar para *reposts* de um usuário):

```ini
PROVIDER=http
HTTP_API_URL=https://api.provedor.com/tiktok/user/reposts?unique_id={username}&count=20
HTTP_API_HEADERS={"Authorization": "Bearer SUA_CHAVE"}
HTTP_API_ITEMS_PATH=data.videos
HTTP_API_ID_FIELD=video_id
```

Dica: rode `check --standalone` e veja o JSON; se aparecer “Não foi possível localizar a lista”, ajuste `HTTP_API_ITEMS_PATH`.

### `apify` — Actor da Apify Store (recomendado para começar)

Só o token é obrigatório:

```ini
PROVIDER=apify
APIFY_TOKEN=apify_api_xxxxxxxx
```

| Variável | Descrição |
|---|---|
| `APIFY_TOKEN` | Token da conta (apify.com → *Settings → API & Integrations*). O plano gratuito tem créditos mensais |
| `APIFY_ACTOR` | Opcional. Padrão: `maximedupre/tiktok-reposts` (lê a aba pública de reposts) |
| `APIFY_INPUT` | Opcional. Padrão: `{"profiles": ["https://www.tiktok.com/@{username}"], "maxItemsPerProfile": 10}` |

Cada verificação executa o Actor (leva de alguns segundos a alguns minutos e consome créditos).
Use `POLL_INTERVAL_SECONDS` ≥ 600 e confira o preço por resultado na página do Actor.
Antes de configurar, teste o Actor no site da Apify com o seu @ e veja se os reposts aparecem.

### `tiktok_research` — API oficial

Endpoint *Query User Reposted Videos* da **TikTok Research API** (acesso só para pesquisadores aprovados).

| Variável | Descrição |
|---|---|
| `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` | Credenciais do app aprovado (token via `client_credentials`) |
| `TIKTOK_RESEARCH_FIELDS` | Campos pedidos (padrão `id,create_time`) |
| `TIKTOK_RESEARCH_MAX_COUNT` | Itens por consulta (padrão 20) |

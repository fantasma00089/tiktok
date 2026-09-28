# TikTok Repost Monitor

Monitora, em tempo quase real, os **reposts** de um perfil do TikTok (por `@` ou `user_id`).
Quando detecta um repost novo:

1. dispara uma **notificação nativa** no PC do servidor (toast do Windows, macOS ou Linux) e atualiza o **painel local**;
2. atualiza o **site estático na Netlify**, que exibe um aviso (banner + modal) com o link do vídeo.

Tudo roda localmente. O agente de IA (**OpenClaw** ou **OpenHands**, com modelo local via Ollama) orquestra e supervisiona o monitor sem depender de créditos de nuvem.

```
TikTok API ──polling──▶ Monitor Python (backend/) ──▶ toast nativo + painel local (http://127.0.0.1:8000)
   (mock / http /            │  estado + log
    apify / research)        ├──▶ GET /status ──tunnel (ngrok/Cloudflare)──▶ site Netlify (fetch)
                             └──▶ deploy de status.json na Netlify (webhook reverso) ──▶ site Netlify
Agente local (OpenClaw / OpenHands) ──▶ inicia, supervisiona, força checagens, abre o vídeo no navegador
```

## Início rápido (5 minutos, sem API)

```bash
# Windows (PowerShell)                          # Linux / macOS
.\scripts\install.ps1                           ./scripts/install.sh
.\scripts\start.ps1                             ./scripts/start.sh
```

Abra o painel em **http://127.0.0.1:8000/**. Com `PROVIDER=mock` (padrão), simule um repost em outro terminal:

```bash
cd backend
.venv/bin/python -m repost_monitor simulate      # Windows: .venv\Scripts\python.exe -m repost_monitor simulate
.venv/bin/python -m repost_monitor check         # ou aguarde o próximo ciclo
```

A notificação nativa aparece, o painel muda para **“Repost detectado agora mesmo”**, e `GET /status` passa a responder `"repostou": true`.

Para ver o site: `cd site && python -m http.server 8080` e abra `http://localhost:8080/?api=http://127.0.0.1:8000`.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `backend/repost_monitor/providers/` | **Módulo de polling**: clientes da API (genérico HTTP/JSON, Apify, TikTok Research API, mock) |
| `backend/repost_monitor/detector.py`, `state.py` | **Módulo de detecção**: compara IDs com o estado salvo (último `item_id` + IDs já vistos) |
| `backend/repost_monitor/notifiers/` | **Módulo de notificação local**: toast nativo, abrir vídeo no navegador |
| `backend/repost_monitor/server.py`, `publishers/` | **Módulo de comunicação com o site**: `GET /status` (tunnel), deploy do `status.json` na Netlify e webhook genérico |
| `backend/repost_monitor/dashboard/` | Painel local (atualiza sozinho via Server‑Sent Events) |
| `backend/repost_monitor/monitor.py`, `cli.py` | Loop de polling com retry/backoff e CLI usada pelo agente |
| `site/` | Site estático (HTML/CSS/JS) para a Netlify |
| `agent/openclaw/` | Skill + instalador do OpenClaw |
| `agent/openhands/` | `docker-compose.yml` do OpenHands + Ollama, tarefa e script de supervisão |
| `tunnel/` | Exemplo de configuração do Cloudflare Tunnel |
| `scripts/` | Instalação, inicialização, autostart no Windows e tunnel |
| `docs/` | Documentação técnica |

## Documentação

- [Instalação](docs/INSTALACAO.md)
- [Configuração (todos os parâmetros)](docs/CONFIGURACAO.md)
- [Arquitetura e fluxo completo](docs/ARQUITETURA.md)
- [Agente de IA local (OpenClaw / OpenHands)](docs/AGENTE.md)
- [Deploy do site na Netlify](docs/NETLIFY.md)
- [Tunnel reverso (ngrok / Cloudflare)](docs/TUNNEL.md)
- [Limitações](docs/LIMITACOES.md)

## Comandos da CLI

Executados em `backend/` com o Python do `.venv`. Todos imprimem JSON (os logs vão para stderr e `backend/logs/`).

| Comando | O que faz | Saída |
|---|---|---|
| `run` | Monitor contínuo + `/status` + painel | — |
| `check` | Um ciclo de polling (delegado ao `run` se ele estiver no ar) | `0` nada novo · `10` repost novo · `1` erro |
| `status` | Status atual | `0` |
| `open-latest` | Abre o último vídeo repostado no navegador | `0`/`1` |
| `test-notification` | Toast de teste | `0`/`1` |
| `simulate` | Adiciona um repost falso (`PROVIDER=mock`) | `0` |
| `publish` | Publica site + `status.json` na Netlify agora | `0`/`1` |
| `doctor` | Valida a configuração | `0`/`1` |

## Testes

```bash
cd backend
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

## Uso responsável

O sistema lê apenas informação que o próprio TikTok torna pública (a aba de reposts de um perfil) e não tenta obter visualizações de perfil, likes ou comentários. Use-o apenas para perfis que você tem legitimidade para acompanhar e respeite os Termos de Uso do TikTok, os termos do provedor de API escolhido e a LGPD.

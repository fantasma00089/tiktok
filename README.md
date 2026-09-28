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

## Início rápido no Windows (5 minutos, sem API)

1. Instale o **Python 3.10+** em https://www.python.org/downloads/ — na primeira tela do instalador,
   marque **“Add python.exe to PATH”**.
2. Baixe o projeto: `git clone -b claude/tiktok-repost-monitoring-agent-a3mngw https://github.com/fantasma00089/tiktok`
   (ou *Code → Download ZIP* no GitHub e extraia).
3. Na pasta do projeto, dê dois cliques em:

| Arquivo | O que faz |
|---|---|
| `instalar.bat` | Cria o ambiente Python, instala as dependências e gera `backend\.env` |
| `iniciar.bat` | Inicia o monitor e abre o painel em http://127.0.0.1:8000/ (feche a janela para parar) |
| `simular-repost.bat` | Com `PROVIDER=mock` (padrão), cria um repost falso: aparece a notificação do Windows e o painel muda para **“Repost detectado agora mesmo”** |

Os `.bat` chamam os scripts do PowerShell com `-ExecutionPolicy Bypass`, então não é preciso mudar a
política de execução. Se preferir o terminal, use `.\scripts\install.ps1` e `.\scripts\start.ps1`
(se aparecer “a execução de scripts foi desabilitada”, rode
`powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1`).

> **Atenção:** com `PROVIDER=mock` (padrão) o programa **não lê o TikTok** — é só simulação, e o painel
> mostra um aviso amarelo. Reposts de verdade só aparecem depois do passo abaixo.

**Monitorar de verdade:** crie uma conta grátis em https://apify.com, copie o token em
*Settings → API & Integrations* e edite `backend\.env` no Bloco de Notas:

```ini
TIKTOK_USERNAME=seu_arroba_sem_o_arroba
PROVIDER=apify
APIFY_TOKEN=cole_o_token_aqui
POLL_INTERVAL_SECONDS=600
```

Feche e abra o `iniciar.bat`. A primeira leitura registra os reposts que já existem sem avisar; os
reposts feitos depois disso geram a notificação. Para testar e ver os reposts atuais logo de cara,
acrescente `BASELINE_ON_FIRST_RUN=false` (depois volte para `true`). Outros provedores:
[CONFIGURACAO.md](docs/CONFIGURACAO.md#provedores).
Para iniciar junto com o Windows: `powershell -ExecutionPolicy Bypass -File .\scripts\register-autostart.ps1`.

### Linux / macOS

```bash
./scripts/install.sh && ./scripts/start.sh --background
cd backend && .venv/bin/python -m repost_monitor simulate && .venv/bin/python -m repost_monitor check
```

Para ver o site localmente: `cd site && python -m http.server 8080` e abra `http://localhost:8080/?api=http://127.0.0.1:8000`.

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
| `*.bat` (raiz) | Atalhos de duplo clique para Windows: instalar, iniciar, simular repost |
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

# TikTok Repost Monitor

Monitora, em tempo quase real, os **reposts** de um perfil do TikTok (por `@` ou `user_id`).
Quando detecta um repost novo:

1. dispara uma **notificação nativa** no PC do servidor (toast do Windows, macOS ou Linux) e atualiza o **painel local**;
2. atualiza o **site estático na Netlify**, que exibe um aviso (banner + modal) com o link do vídeo.

Tudo roda localmente. O agente de IA (**OpenClaw** ou **OpenHands**, com modelo local via Ollama) orquestra e supervisiona o monitor sem depender de créditos de nuvem.

```
TikTok (aba Reposts) ──navegador──▶ Monitor Python (backend/) ──▶ toast nativo + painel local (http://127.0.0.1:8000)
   (ou API: http /            │  estado + log
    apify / research)         ├──▶ GET /status ──tunnel (ngrok/Cloudflare)──▶ site Netlify (fetch)
                             └──▶ deploy de status.json na Netlify (webhook reverso) ──▶ site Netlify
Agente local (OpenClaw / OpenHands) ──▶ inicia, supervisiona, força checagens, abre o vídeo no navegador
```

## Início rápido no Windows

Sem API e sem conta: o monitor abre o perfil num **navegador invisível** (o Microsoft Edge que já vem
no Windows), entra na aba **Reposts** e compara com a verificação anterior. Imagens e vídeos não são
carregados, e o navegador fecha depois de cada verificação.

1. Instale o **Python 3.10+** em https://www.python.org/downloads/ — na primeira tela do instalador,
   marque **“Add python.exe to PATH”**.
2. No GitHub, clique em **Code → Download ZIP** e extraia.
3. Dê dois cliques em **`instalar.bat`**.
4. Abra `backend\.env` no Bloco de Notas e coloque o @ do perfil (o que aparece depois do @ no link
   `tiktok.com/@perfil`, **não** o nome de exibição):
   ```ini
   TIKTOK_USERNAME=perfil
   ```
5. Dê dois cliques em **`iniciar.bat`**: o painel abre em http://127.0.0.1:8000/. Deixe a janela aberta
   (fechar a janela para o monitor).

A primeira verificação só registra os reposts que já existem. Os reposts feitos **depois** disso
geram a notificação do Windows e o aviso no painel.

| Atalho | Para quê |
|---|---|
| `instalar.bat` | Instala (ou reinstala) tudo |
| `iniciar.bat` | Inicia o monitor e abre o painel |
| `verificar-agora.bat` | Verifica agora, sem esperar o próximo ciclo (com o `iniciar.bat` aberto ou não) |
| `abrir-navegador.bat` | Mostra o navegador do monitor, para fazer login ou resolver captcha se o TikTok pedir |
| `testar-notificacao.bat` | Mostra uma notificação de teste do Windows |

Requisitos do perfil monitorado: a aba de reposts precisa estar **pública**
(TikTok → Configurações → Privacidade → Vídeos repostados). Para iniciar junto com o Windows:
`powershell -ExecutionPolicy Bypass -File .\scripts\register-autostart.ps1`.

### Linux / macOS

```bash
./scripts/install.sh            # instala também o Chromium do Playwright
./scripts/start.sh
```

Para ver o site localmente: `cd site && python -m http.server 8080` e abra `http://localhost:8080/?api=http://127.0.0.1:8000`.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `backend/repost_monitor/providers/` | **Módulo de polling**: navegador local (padrão, sem API), genérico HTTP/JSON, Apify, TikTok Research API, simulação |
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
| `*.bat` (raiz) | Atalhos de duplo clique para Windows |
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
| `abrir-navegador` | Abre o navegador do monitor visível (login/captcha) | `0` |
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

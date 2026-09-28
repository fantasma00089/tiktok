# Instalação

## Pré-requisitos

| Item | Para quê | Obrigatório |
|---|---|---|
| Python 3.10+ | Monitor (backend) | Sim |
| Conta Netlify (gratuita) | Hospedar o site | Sim |
| `cloudflared` ou `ngrok` | Tunnel reverso (modo tunnel) | Só no modo tunnel |
| Node.js 22+ | OpenClaw | Se usar OpenClaw |
| Docker Desktop / Docker Engine | OpenHands + Ollama | Se usar OpenHands |
| Ollama | Modelo de linguagem local para o agente | Sim, para o agente |
| `notify-send` (pacote `libnotify-bin`) | Notificação nativa no Linux | Só no Linux |

No Windows e no macOS a notificação nativa não precisa de nada extra.

## 1. Backend (monitor)

```powershell
# Windows
.\scripts\install.ps1
```
```bash
# Linux / macOS
./scripts/install.sh
```

O script cria `backend/.venv`, instala as dependências (`fastapi`, `uvicorn`, `httpx`) e copia
`backend/.env.example` para `backend/.env`. Edite pelo menos:

```ini
TIKTOK_USERNAME=perfil_que_voce_quer_monitorar
PROVIDER=mock          # troque por http / apify / tiktok_research quando tiver a API
```

Valide e inicie:

```bash
cd backend
.venv/bin/python -m repost_monitor doctor
../scripts/start.sh                     # Windows: ..\scripts\start.ps1
```

Painel local: http://127.0.0.1:8000/ · Status público: http://127.0.0.1:8000/status

### Iniciar com o Windows

```powershell
.\scripts\register-autostart.ps1
```
Cria a tarefa agendada `TikTokRepostMonitor`, que roda o monitor em segundo plano (sem janela) a cada logon.

## 2. Teste de ponta a ponta sem API

Com `PROVIDER=mock`:

```bash
cd backend
.venv/bin/python -m repost_monitor test-notification   # confere o toast
.venv/bin/python -m repost_monitor simulate            # cria um repost falso
.venv/bin/python -m repost_monitor check               # detecta: código de saída 10
```

A primeira leitura só registra os reposts que já existem (sem alerta). Por isso, o
`simulate` feito **depois** que o monitor já está rodando é o que gera a notificação.

## 3. Provedor real de dados

Veja [CONFIGURACAO.md](CONFIGURACAO.md#provedores) e escolha `http`, `apify` ou `tiktok_research`.

## 4. Site e comunicação

1. [Publique o site na Netlify](NETLIFY.md).
2. Escolha **uma** forma de o site receber o status:
   - **Tunnel** ([TUNNEL.md](TUNNEL.md)): o site consulta `https://<tunnel>/status` a cada 30s. Tempo real.
   - **Webhook reverso** ([NETLIFY.md](NETLIFY.md#modo-webhook-reverso)): o monitor publica `status.json` na Netlify quando detecta um repost. Não expõe o PC na internet.

   Dá para usar as duas: o site tenta o tunnel primeiro e cai para o `status.json`.

## 5. Agente de IA local

Siga [AGENTE.md](AGENTE.md) para instalar o OpenClaw (recomendado) ou o OpenHands via Docker.

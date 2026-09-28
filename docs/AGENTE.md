# Agente de IA local (OpenClaw / OpenHands)

O agente é o **orquestrador**: ele inicia e supervisiona o monitor, força checagens, reage a reposts
novos (abrindo o vídeo no navegador) e diagnostica falhas. O polling em si é executado pelo
monitor Python — veja [por quê](ARQUITETURA.md#por-que-o-polling-não-é-feito-pelo-próprio-llm).

Nenhuma das opções usa API paga: o modelo de linguagem roda localmente pelo **Ollama**.

| | OpenClaw (recomendado) | OpenHands |
|---|---|---|
| Onde roda | Direto no host (Node.js) | Docker (sandbox isolado) |
| Acesso ao PC | Executa comandos no host: inicia o monitor, abre o navegador | Só pela API HTTP do monitor |
| Agendamento | `openclaw cron` nativo | Script em loop dentro do sandbox |
| Instalação | `agent/openclaw/install.ps1` / `.sh` | `agent/openhands/docker-compose.yml` |

## Modelo local (Ollama)

1. Instale o Ollama: https://ollama.com/download (ou use o serviço `ollama` do `docker-compose.yml`).
2. Baixe um modelo com suporte a *tool calling*. Para PCs modestos, um modelo de ~7–8B funciona para
   esta tarefa (ex.: `ollama pull qwen2.5-coder:7b`); com GPU melhor, prefira modelos maiores
   recomendados na documentação do agente.

A tarefa do agente é curta e guiada por comandos com saída JSON e códigos de saída, o que torna
modelos pequenos suficientes.

## Opção A — OpenClaw

```powershell
# Windows
.\agent\openclaw\install.ps1
```
```bash
# Linux / macOS
./agent/openclaw/install.sh
```

O instalador:
1. instala o OpenClaw com `npm install -g openclaw@latest` (se ainda não existir) — em seguida rode
   `openclaw onboard --install-daemon` e escolha **Ollama** como provedor do modelo;
2. copia a skill `agent/openclaw/skills/tiktok-repost-monitor/` para `~/.openclaw/workspace/skills/`
   (mude com `OPENCLAW_SKILLS_DIR`);
3. cria o job `tiktok-repost-supervisor` com `openclaw cron add --every 15m --session isolated`
   (mude com `SUPERVISE_EVERY`), que garante que o monitor está no ar e roda um `check`.

Teste manual:
```bash
openclaw agent --message "Use a skill tiktok-repost-monitor com REPOST_MONITOR_HOME=/caminho/do/repo e verifique reposts agora."
```

Se a criação automática do job falhar (a CLI do OpenClaw evolui rápido), crie-o pela interface do
OpenClaw com a mesma mensagem usada no `install.sh`.

## Opção B — OpenHands (Docker)

```bash
cd agent/openhands
cp .env.example .env
docker compose up -d
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

1. No `backend/.env`, defina `HOST=0.0.0.0` e um `ADMIN_TOKEN` longo e aleatório, e reinicie o monitor.
   (O sandbox do OpenHands acessa o monitor por `http://host.docker.internal:8000`, que não é loopback.)
2. Abra http://localhost:3000 → **Settings → LLM → Advanced**:
   - *Custom Model*: `ollama/qwen2.5-coder:7b`
   - *Base URL*: `http://host.docker.internal:11434`
   - *API Key*: `ollama` (qualquer valor)
3. Inicie uma conversa conectando este repositório (ou montando-o em `/workspace`) e cole a tarefa de
   [`agent/openhands/TASK.md`](../agent/openhands/TASK.md).
4. O agente executa `agent/openhands/supervise.sh`, que chama `POST /api/check-now` a cada 5 minutos
   e imprime `REPOST_NOVO <url>` quando há novidade.

Observações:
- A versão do OpenHands é fixada por `OPENHANDS_VERSION` em `agent/openhands/.env`; confira a mais
  recente em https://github.com/OpenHands/OpenHands/releases. Em versões antigas (0.x) as variáveis
  do runtime eram `SANDBOX_RUNTIME_CONTAINER_IMAGE`.
- Com `HOST=0.0.0.0`, as rotas `/api/*` exigem o `ADMIN_TOKEN` para qualquer acesso que não venha do
  próprio PC. Mantenha o firewall do sistema bloqueando a porta 8000 para a rede externa.
- Como o sandbox é isolado, as notificações nativas continuam sendo feitas pelo monitor no host.

## Sem agente

O monitor funciona sozinho (`scripts/start.*` + `register-autostart.ps1`). O agente acrescenta
supervisão, reinício automático e ações no navegador.

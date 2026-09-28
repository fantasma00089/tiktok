# Tarefa para o OpenHands — supervisor do monitor de reposts

Cole o texto abaixo em uma nova conversa do OpenHands (http://localhost:3000).
Substitua `SEU_ADMIN_TOKEN` pelo valor de `ADMIN_TOKEN` do `backend/.env`.

---

Você é o supervisor de um monitor de reposts do TikTok que roda no host.
Não escreva textos longos: execute ações e informe o resultado em uma linha.

API do monitor: `http://host.docker.internal:8000`
Cabeçalho obrigatório: `Authorization: Bearer SEU_ADMIN_TOKEN`

1. Verifique se o monitor está no ar:
   `curl -s http://host.docker.internal:8000/health`
   Se falhar, responda "Monitor fora do ar — inicie scripts/start no host" e pare.
2. Rode o script de supervisão (fica em execução e reage a reposts):
   `bash /workspace/agent/openhands/supervise.sh`
   (o diretório do repositório deve estar montado em /workspace; se não estiver,
   crie o script a partir do conteúdo de agent/openhands/supervise.sh)
3. Quando o script imprimir `REPOST_NOVO <url>`, responda apenas com essa linha.
4. Se imprimir `ERRO`, leia o campo `erro`; se for HTTP 429, apenas aguarde.
   Caso contrário, informe o erro em uma linha.

Não tente obter visualizações de perfil, likes ou comentários.

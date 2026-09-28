# Deploy do site na Netlify

O site (`site/`) é só HTML, CSS e JavaScript — sem build, sem funções, sem backend na Netlify.

| Arquivo | Função |
|---|---|
| `index.html`, `styles.css`, `app.js` | Página, estilo e lógica (consulta o status e mostra banner/modal) |
| `config.js` | **Edite aqui** a URL do tunnel e o intervalo de consulta |
| `status.json` | Status inicial; substituído pelo monitor no modo webhook reverso |
| `_headers` | Desliga o cache do `status.json` |
| `netlify.toml` | Declara que não há build |

## 1. Configure o `config.js`

```js
window.REPOST_CONFIG = {
  TUNNEL_URL: "https://status.seudominio.com", // vazio = só status.json
  POLL_INTERVAL_MS: 30000,
  REQUEST_TIMEOUT_MS: 8000,
};
```

Para testar outra URL sem novo deploy: `https://seu-site.netlify.app/?api=https://abc.trycloudflare.com`.

## 2. Publique

Escolha uma opção:

- **Arrastar e soltar**: em https://app.netlify.com/drop, arraste a pasta `site/`.
- **Netlify CLI**:
  ```bash
  npm install -g netlify-cli
  netlify login
  cd site
  netlify deploy --prod --dir .
  ```
- **Git**: conecte o repositório em *Add new site → Import an existing project* e defina
  *Base directory* = `site`, *Publish directory* = `site` e *Build command* vazio.

## 3. Restrinja o CORS (recomendado)

No `backend/.env`: `CORS_ORIGINS=https://seu-site.netlify.app`.

## Modo webhook reverso

Neste modo o PC **não** fica exposto: quando detecta um repost, o monitor faz um deploy na Netlify
contendo o `status.json` atualizado. O site lê `./status.json` do próprio domínio.

1. Crie um token em *User settings → Applications → Personal access tokens*.
2. Copie o *Site ID* em *Site configuration → General → Site details*.
3. No `backend/.env`:
   ```ini
   NETLIFY_AUTH_TOKEN=nfp_xxxxxxxx
   NETLIFY_SITE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   NETLIFY_SITE_DIR=../site
   ```
4. Teste: `python -m repost_monitor publish`.

Como funciona: o monitor usa a API de deploy por *file digest* — envia o SHA1 de cada arquivo e só
faz upload dos que mudaram (normalmente apenas o `status.json`). Por isso a pasta `site/` do PC é a
fonte do site: edite-a e rode `publish` para atualizar.

Limites: a Netlify limita a quantidade de deploys por minuto e por dia. O monitor publica apenas ao
iniciar e quando há repost novo, respeita `NETLIFY_MIN_INTERVAL_SECONDS` e agrupa pedidos próximos.
Se usar `NETLIFY_HEARTBEAT_MINUTES`, mantenha valores altos (≥ 60).

Diferenças em relação ao tunnel:

| | Tunnel | Webhook reverso |
|---|---|---|
| Latência até o site | ≤ intervalo de consulta do site (30s) | tempo do deploy (segundos) + 30s |
| PC exposto na internet | Sim (só `/status`) | Não |
| Mostra “monitor online” | Sim | Só com heartbeat |
| Funciona com o PC desligado | Não (site mostra “não foi possível obter o status”) | Mostra o último status publicado |

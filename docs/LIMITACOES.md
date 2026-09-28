# Limitações

## Da plataforma TikTok

- **Não existe webhook de reposts.** O TikTok não notifica terceiros quando alguém reposta um vídeo.
  Polling periódico é a única abordagem viável; por isso a detecção é *quase* em tempo real —
  o atraso máximo é aproximadamente `POLL_INTERVAL_SECONDS` (+ o intervalo de consulta do site).
- **Não é possível detectar visualizações de perfil.** Essa informação não é exposta por nenhuma API
  (é uma configuração de privacidade do próprio app) e o sistema não tenta obtê-la.
- **Somente reposts.** Likes, comentários, views e outras interações estão fora do escopo.
- **Aba de reposts precisa estar visível.** Se o perfil for privado ou ocultar os reposts, nenhuma API
  consegue lê-los — o monitor apenas continuará “Aguardando repost”.
- **A ordem da lista de reposts não é garantida.** Por isso a detecção compara o conjunto de IDs já
  vistos, e não apenas o primeiro item.
- **Falha na primeira leitura**: se a API devolver uma lista vazia por engano justamente na primeira
  leitura, a base fica vazia e os reposts antigos serão notificados uma vez na leitura seguinte.
- **Repost desfeito não gera alerta**, e se o mesmo vídeo for repostado de novo depois ele não é
  considerado novo (o ID já foi visto).

## Do modo navegador (padrão)

- Depende do layout do site do TikTok: se o TikTok mudar a aba de reposts, o monitor mostra o erro
  “Não encontrei a aba de reposts” até ser ajustado (`providers/browser.py`).
- O TikTok pode pedir captcha ou login de vez em quando; resolva uma vez pelo `abrir-navegador.bat`.
- Verificar com muita frequência aumenta a chance de captcha: mantenha `POLL_INTERVAL_SECONDS` ≥ 120.
- Cada verificação abre o navegador por alguns segundos (uso de CPU/memória só durante esse tempo).

## Das APIs

- **API oficial (Research API)**: disponível apenas para pesquisadores aprovados pelo TikTok, com cotas diárias.
- **APIs não oficiais (PrimeApi, YepAPI, RapidAPI, Apify...)**: dependem de scraping; podem mudar o
  formato da resposta, ficar fora do ar ou atrasar dados. Os planos gratuitos têm limites de
  requisições/créditos — ajuste `POLL_INTERVAL_SECONDS` de acordo. O uso delas está sujeito aos termos
  do TikTok e do próprio provedor.
- O requisito “sem APIs pagas” vale para o agente e a infraestrutura; a fonte de dados usa o **plano
  gratuito** do provedor escolhido (ou o modo `mock` para testes).

## Do sistema

- O PC precisa estar ligado e com internet. No modo tunnel, o site mostra “Não foi possível obter o status”
  quando o PC está desligado; no modo webhook reverso, mostra o último status publicado.
- A Netlify limita a quantidade de deploys (modo webhook reverso); o monitor publica só quando necessário.
- URLs de Quick Tunnel (`trycloudflare.com`) e do ngrok gratuito sem domínio mudam a cada execução.
- O agente de IA com modelo local é mais lento e menos confiável que modelos em nuvem; por isso ele
  supervisiona e age sobre resultados determinísticos, em vez de fazer o polling.
- Notificação nativa no Linux depende do `notify-send`. No Windows, o toast usa o Windows PowerShell 5.1
  (`powershell.exe`), presente em todas as instalações do Windows 10/11.

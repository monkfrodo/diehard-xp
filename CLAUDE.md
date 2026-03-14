# Diehard XP — Ranking de Experiência da Guild

## O que é

Sistema de tracking de XP (experiência) para a guild **Diehard** no servidor **Luminera** do MMORPG Tibia. Um scraper Python coleta dados de XP diariamente das APIs do TibiaData e GuildStats.eu, gera JSONs, e um frontend estático exibe o ranking com abas de período (ontem, 7 dias, 30 dias).

Feito para motivar os membros da guild a caçar XP e acompanhar o progresso.

## Stack

- **Scraper:** Python 3 (requests, BeautifulSoup4)
- **Anti-bot:** cloudscraper, curl_cffi, Playwright (fallback em cascata)
- **Frontend:** HTML + CSS + JS vanilla (single-file, 39k linhas)
- **Admin:** HTML separado (`admin.html`) para gerenciar extras
- **Dados:** JSON (ranking.json, status.json, extras.json, frases.json)
- **Screenshot:** html2canvas (CDN) para gerar imagem do ranking
- **Deploy:** GitHub Pages (estático)
- **Automação:** GitHub Actions (cron diário)

## Domínio

Hospedado no GitHub Pages do repositório. Sem domínio personalizado.

## Deploy

O deploy é automático via GitHub Pages. Basta fazer push na `main`.

### Atualização de dados

Os dados são atualizados automaticamente pelo GitHub Actions (cron) ou manualmente:

```bash
# Rodar scraper localmente
pip install requests beautifulsoup4 cloudscraper
python scraper/buscar_dados.py

# Servir localmente
python -m http.server 8000
```

## Comandos

```bash
# Instalar dependências Python
pip install requests beautifulsoup4

# Para bypass anti-bot (opcional, em cascata)
pip install cloudscraper
pip install curl_cffi
pip install playwright && playwright install chromium

# Rodar o scraper
python scraper/buscar_dados.py

# Servir frontend localmente
python -m http.server 8000
```

## Variáveis de Ambiente

Nenhuma. O scraper usa APIs públicas.

## Estrutura de Pastas

```
diehard-xp/
├── index.html              ← Frontend principal (ranking, ~39k linhas, single-file)
├── admin.html              ← Painel admin (gerenciar extras, ~26k linhas)
├── scraper/
│   ├── buscar_dados.py     ← Scraper principal (17k linhas, retry logic)
│   └── http_client.py      ← Cliente HTTP com fallback anti-bot (3k linhas)
├── dados/
│   ├── ranking.json        ← Dados do ranking (gerado pelo scraper)
│   ├── status.json         ← Status da execução (validação, timestamps)
│   ├── extras.json         ← Lista de jogadores fora da guild a trackear
│   ├── frases.json         ← Frases motivacionais para o ranking
│   └── debug_guildstats.html  ← HTML raw do GuildStats (debug)
├── prototipos/             ← 11 protótipos de design testados
│   ├── papel.html          ← Versão "papel" (a escolhida)
│   ├── arena.html, elite.html, race.html, etc.
├── .github/
│   └── workflows/
│       ├── atualizar.yml   ← Cron diário 7h BRT (10:00 UTC), timeout 210min
│       └── deploy.yml      ← Deploy para GitHub Pages
├── .claude/
│   └── settings.local.json ← Config local do Claude
├── .gitignore              ← __pycache__, .env, *.log
└── CLAUDE.md               ← Este arquivo
```

## Fluxo de Dados

1. **GitHub Actions** roda `scraper/buscar_dados.py` diariamente às 7h BRT
2. **Scraper** busca dados de 2 fontes:
   - **TibiaData API** (`api.tibiadata.com`): lista de membros, vocações, levels
   - **GuildStats.eu** (`guildstats.eu`): XP de ontem, 7 dias e 30 dias
3. **http_client.py** tenta 3 estratégias anti-bot em cascata: cloudscraper → curl_cffi → Playwright
4. **Retry logic:** Até 36 tentativas com 5min de intervalo (GuildStats atualiza de forma assíncrona). Considera dados válidos quando 10+ membros têm XP positivo para "ontem"
5. **Output:** Gera `ranking.json` e `status.json` em `dados/`
6. **Extras:** Jogadores em `dados/extras.json` são buscados individualmente nas páginas de character do GuildStats
7. **Frontend** (`index.html`) carrega `dados/ranking.json` via fetch e renderiza

## Frontend (index.html)

- **Design:** Estilo "papel de caderno" — fundo creme, linhas horizontais, margem vermelha
- **Fontes:** Kalam (corpo cursivo) + Caveat (títulos/nomes)
- **Abas:** Ontem, 7 dias, 30 dias (filtra ranking por período)
- **Status banner:** Verde (dados OK) ou amarelo pulsante (aguardando atualização)
- **Screenshot:** Botão que usa html2canvas para gerar PNG do ranking
- **Cores por vocação:** Cada vocação do Tibia tem cor distinta

## Admin (admin.html)

- Painel para gerenciar a lista `extras.json` (jogadores fora da guild)
- Design limpo com Inter font
- Permite adicionar/remover jogadores extras

## Regras de Desenvolvimento

### Fazer
- Manter compatibilidade com GitHub Actions (timeout 210min)
- Testar scraper com `--dry-run` ou execução local antes de alterar lógica
- Preservar retry logic (GuildStats é instável)
- Manter fallback em cascata no http_client.py

### Não fazer
- Não alterar o cron schedule sem verificar timezone BRT vs UTC
- Não remover protótipos — servem como referência de design
- Não commitar `__pycache__/` ou arquivos `.pyc`
- Não hardcodar nomes de membros — a lista vem da TibiaData API
- Não remover o sistema de extras — jogadores saem e voltam da guild

## Dados Importantes

- **Guild:** Diehard
- **Servidor:** Luminera (Tibia)
- **Timezone:** America/Sao_Paulo (BRT)
- **Fontes de dados:** TibiaData API (pública) + GuildStats.eu (scraping)

## Contexto

Projeto pessoal do Kevin para a guild de Tibia que ele participa. Não tem relação com a Íntegros. É usado pelos membros da guild para acompanhar quem está caçando mais XP e criar competição saudável.

## Git

- **Branch:** `main`
- **Commits:** conventional commits em inglês
- **CI/CD:** GitHub Actions (atualizar.yml + deploy.yml)

# 🏰 Diehard Guild - Ranking de XP

Sistema de tracking de experiência para a guild **Diehard** no servidor **Luminera** (Tibia).

## ✨ Funcionalidades

- **Rankings**: Ontem, 7 dias, 30 dias e Consolidado
- **Filtros**: Todos, 500+ ou até 500
- **Screenshot**: Gera imagem do Top 20
- **Mobile**: Mostra XP de Ontem no consolidado (ordenação principal)
- **Extras**: Trackeamento de jogadores fora da guild

## 🔄 Atualização Automática

- **Horário**: 7h da manhã (Brasília) via GitHub Actions
- **Fontes**: GuildStats.eu (XP) + TibiaData API (vocações/levels)

## 📁 Estrutura

```
diehard-xp-main/
├── index.html                    # Interface web
├── scraper/
│   └── buscar_dados.py          # Script de coleta
├── dados/
│   ├── ranking.json             # Dados (gerado automaticamente)
│   ├── extras.json              # Lista de extras
│   └── debug_guildstats.html    # HTML para debug
└── .github/workflows/
    └── atualizar.yml            # GitHub Actions
```

## ➕ Extras

Edite `dados/extras.json` para adicionar jogadores **fora da guild**:

```json
{
  "extras": [
    {"nome": "Nome do Jogador"}
  ]
}
```

⚠️ **NÃO coloque membros da guild aqui** - eles são puxados automaticamente!

## 🛠️ Desenvolvimento

```bash
pip install requests beautifulsoup4
python scraper/buscar_dados.py
python -m http.server 8000
```

## 🔗 Links

- [GuildStats](https://guildstats.eu/guild?guild=Diehard)
- [Tibia.com](https://www.tibia.com/community/?subtopic=guilds&page=view&GuildName=Diehard)

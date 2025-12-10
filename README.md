# ⚔️ Diehard Guild - Ranking XP

Ranking de experiência da guild **Diehard** (Luminera) com dados de **ontem**, **7 dias** e **30 dias**.

---

## 🔄 COMO FORÇAR ATUALIZAÇÃO MANUAL

1. Vá no seu repositório no GitHub
2. Clique na aba **"Actions"** (no menu superior)
3. No menu lateral esquerdo, clique em **"Atualizar Ranking"**
4. Clique no botão azul **"Run workflow"** (lado direito)
5. Clique novamente em **"Run workflow"** no dropdown
6. Aguarde ~2 minutos e atualize sua página!

> ⚠️ **Se não aparecer o botão "Run workflow"**: O arquivo `.github/workflows/atualizar.yml` pode não ter sido enviado corretamente. Certifique-se de que a pasta `.github` (com o ponto!) existe no seu repositório.

---

## 📁 Estrutura de Arquivos

```
diehard-xp/
├── .github/
│   └── workflows/
│       └── atualizar.yml    ← Automação (IMPORTANTE: pasta com ponto!)
├── scraper/
│   └── buscar_dados.py      ← Script Python
├── dados/
│   ├── extras.json          ← Jogadores de fora da guild
│   └── ranking.json         ← Dados do ranking
├── index.html               ← Página web
└── README.md
```

---

## 👥 Jogadores Extras

Edite `dados/extras.json` para adicionar jogadores que estão temporariamente fora da guild:

```json
{
  "extras": [
    {"nome": "Nome Exato Do Char"},
    {"nome": "Outro Char"}
  ]
}
```

---

## ⏰ Atualização Automática

O ranking atualiza automaticamente todos os dias às **6:30 AM** (horário de Brasília).

---

## 📜 Créditos

- [GuildStats.eu](https://guildstats.eu) - Dados de XP
- [TibiaData API](https://tibiadata.com) - Vocações
- [GitHub Pages](https://pages.github.com) - Hospedagem

**Diehard** ⚔️ Luminera

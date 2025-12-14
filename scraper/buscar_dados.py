#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
import time

GUILD_NAME = “Diehard”
WORLD = “Luminera”

# URL CORRIGIDA - era “guild=” mas deve ser “guild?guild=”

GUILDSTATS_URL = f”https://guildstats.eu/guild?guild={GUILD_NAME}&op=3”

def parse_exp_value(exp_str):
“”“Converte string de XP para inteiro.”””
if not exp_str or exp_str.strip() in [’*-*’, ‘-’, ‘’, ‘0’]:
return 0
clean = exp_str.strip().replace(’,’, ‘’).replace(’.’, ‘’).replace(’+’, ‘’).replace(’ ‘, ‘’)
is_negative = clean.startswith(’-’)
clean = clean.replace(’-’, ‘’)
try:
return -int(clean) if is_negative else int(clean)
except:
return 0

def buscar_vocacoes_guild_tibiadata():
“”“Busca vocações e levels de todos os membros da guild via TibiaData API.”””
print(“Buscando vocações da guild via TibiaData API…”)
vocacoes = {}
try:
url = f”https://api.tibiadata.com/v4/guild/{GUILD_NAME}”
resp = requests.get(url, timeout=30)
if resp.status_code == 200:
data = resp.json()
if ‘guild’ in data and ‘members’ in data[‘guild’]:
for member in data[‘guild’][‘members’]:
nome_lower = member.get(‘name’, ‘’).lower()
vocacoes[nome_lower] = {
‘vocation’: member.get(‘vocation’, ‘’),
‘level’: member.get(‘level’, 0)
}
print(f”  ✓ {len(vocacoes)} vocações carregadas”)
except Exception as e:
print(f”  ERRO: {e}”)
return vocacoes

def buscar_vocacao_individual(nome, tentativa=1):
“”“Busca vocação de um jogador específico (para extras).”””
try:
import urllib.parse
nome_encoded = urllib.parse.quote(nome)
url = f”https://api.tibiadata.com/v4/character/{nome_encoded}”

```
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    resp = requests.get(url, headers=headers, timeout=15)
    
    if resp.status_code == 200:
        data = resp.json()
        char = data.get('character', {}).get('character', {})
        if char and char.get('name'):
            return {
                'vocation': char.get('vocation', ''),
                'level': char.get('level', 0)
            }
        else:
            print(f"    Resposta sem dados: {str(data)[:150]}")
    elif resp.status_code == 429 and tentativa < 3:
        # Rate limited - espera e tenta novamente
        print(f"    Rate limited, aguardando...")
        time.sleep(5)
        return buscar_vocacao_individual(nome, tentativa + 1)
    else:
        print(f"    HTTP {resp.status_code}")
except Exception as e:
    print(f"    Erro: {e}")
    if tentativa < 3:
        time.sleep(2)
        return buscar_vocacao_individual(nome, tentativa + 1)
return None
```

def buscar_exp_guildstats(nome):
“”“Busca XP de um jogador na página individual do GuildStats (tab=9).”””
try:
import urllib.parse
url = f”https://guildstats.eu/character?nick={urllib.parse.quote(nome)}&tab=9”
headers = {‘User-Agent’: ‘Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36’}
resp = requests.get(url, headers=headers, timeout=15)

```
    if resp.status_code != 200:
        return None
    
    if "does not exsists" in resp.text or "don't have in our datebase" in resp.text:
        print(f"    {nome}: não existe no GuildStats")
        return None
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    exp_values = []
    
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                date_cell = cells[0].text.strip()
                exp_cell = cells[1].text.strip()
                
                if len(date_cell) == 10 and date_cell[4] == '-' and date_cell[7] == '-':
                    exp_value = parse_exp_value(exp_cell)
                    exp_values.append(exp_value)
    
    if not exp_values:
        print(f"    {nome}: nenhum dado de XP encontrado")
        return None
    
    exp_yesterday = exp_values[-1] if len(exp_values) >= 1 else 0
    exp_7days = sum(exp_values[-7:]) if len(exp_values) >= 1 else 0
    exp_30days = sum(exp_values[-30:]) if len(exp_values) >= 1 else 0
    
    print(f"    ✓ XP: ontem={exp_yesterday:,}, 7d={exp_7days:,}, 30d={exp_30days:,}")
    return {
        'exp_yesterday': exp_yesterday,
        'exp_7days': exp_7days,
        'exp_30days': exp_30days
    }
    
except Exception as e:
    print(f"    Erro buscando XP de {nome}: {e}")
return None
```

def buscar_dados_guild():
“”“Busca dados de XP da guild no GuildStats (página op=3).”””
print(f”Buscando dados de XP do GuildStats…”)
print(f”  URL: {GUILDSTATS_URL}”)
headers = {‘User-Agent’: ‘Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36’}
resp = requests.get(GUILDSTATS_URL, headers=headers, timeout=30)
resp.raise_for_status()

```
soup = BeautifulSoup(resp.text, 'html.parser')
jogadores = []

for row in soup.find_all('tr'):
    cols = row.find_all('td')
    if len(cols) < 15:
        continue
    
    char_link = None
    for col in cols:
        link = col.find('a')
        if link and 'character?nick=' in str(link.get('href', '')):
            char_link = link
            break
    
    if not char_link:
        continue
    
    nome = char_link.text.strip()
    
    level = 0
    level_text = cols[2].text.strip()
    if level_text.isdigit():
        level = int(level_text)
    
    exp_yesterday = parse_exp_value(cols[-4].text.strip())
    exp_7days = parse_exp_value(cols[-3].text.strip())
    exp_30days = parse_exp_value(cols[-2].text.strip())
    
    jogadores.append({
        'name': nome,
        'level': level,
        'exp_yesterday': exp_yesterday,
        'exp_7days': exp_7days,
        'exp_30days': exp_30days,
        'vocation': '',
        'is_extra': False
    })

print(f"  ✓ {len(jogadores)} jogadores encontrados na guild")
return jogadores
```

def carregar_extras():
“”“Carrega lista de extras do arquivo JSON.”””
possiveis_caminhos = [
os.path.join(os.path.dirname(os.path.abspath(**file**)), ‘..’, ‘dados’, ‘extras.json’),
os.path.join(os.getcwd(), ‘dados’, ‘extras.json’),
‘dados/extras.json’
]

```
for caminho in possiveis_caminhos:
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                data = json.load(f)
                extras = [e.get('nome', '') for e in data.get('extras', []) if e.get('nome')]
                print(f"  ✓ {len(extras)} extras carregados de {caminho}")
                return extras
        except Exception as e:
            print(f"  Erro ao ler {caminho}: {e}")

print("  ✗ Nenhum arquivo extras.json encontrado")
return []
```

def main():
print(”=” * 60)
print(f”Atualizando ranking: {GUILD_NAME}”)
print(f”Hora: {datetime.now().strftime(’%Y-%m-%d %H:%M:%S’)}”)
print(”=” * 60)

```
# 1. Busca vocações da guild
vocacoes_guild = buscar_vocacoes_guild_tibiadata()

# 2. Busca dados de XP da guild
jogadores = buscar_dados_guild()

# 3. Aplica vocações
print("\nAplicando vocações...")
for jogador in jogadores:
    nome_lower = jogador['name'].lower()
    if nome_lower in vocacoes_guild:
        jogador['vocation'] = vocacoes_guild[nome_lower]['vocation']
        if jogador['level'] == 0:
            jogador['level'] = vocacoes_guild[nome_lower]['level']

# 4. Processa extras
print("\nCarregando extras...")
extras = carregar_extras()

if extras:
    print(f"\nProcessando {len(extras)} extras:")
    for i, nome in enumerate(extras):
        print(f"  → {nome} ({i+1}/{len(extras)})")
        
        # Delay entre requisições para evitar rate limiting
        if i > 0:
            time.sleep(1)
        
        # Busca vocação
        dados = buscar_vocacao_individual(nome)
        if not dados:
            print(f"    ✗ Não encontrado no TibiaData")
            continue
        
        print(f"    Level {dados['level']}, {dados['vocation']}")
        
        # Busca XP
        exp = buscar_exp_guildstats(nome)
        time.sleep(1)  # Rate limiting
        
        jogadores.append({
            'name': nome,
            'level': dados['level'],
            'vocation': dados['vocation'],
            'exp_yesterday': exp['exp_yesterday'] if exp else 0,
            'exp_7days': exp['exp_7days'] if exp else 0,
            'exp_30days': exp['exp_30days'] if exp else 0,
            'is_extra': True
        })

# 5. Cria rankings (sem limite)
def criar_ranking(jogadores, campo):
    filtrados = [j for j in jogadores if j.get(campo, 0) > 0]
    filtrados.sort(key=lambda x: x.get(campo, 0), reverse=True)
    return [{
        'rank': i,
        'name': j['name'],
        'vocation': j['vocation'],
        'level': j['level'],
        'points': j[campo],
        'is_extra': j.get('is_extra', False)
    } for i, j in enumerate(filtrados, 1)]

dados_finais = {
    'guild': GUILD_NAME,
    'world': WORLD,
    'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'last_update_display': datetime.now().strftime('%d/%m/%Y às %H:%M'),
    'total_members': len([j for j in jogadores if not j.get('is_extra')]),
    'rankings': {
        'yesterday': criar_ranking(jogadores, 'exp_yesterday'),
        '7days': criar_ranking(jogadores, 'exp_7days'),
        '30days': criar_ranking(jogadores, 'exp_30days')
    }
}

# Salva o arquivo
output_path = os.path.join(os.getcwd(), 'dados', 'ranking.json')
os.makedirs(os.path.dirname(output_path), exist_ok=True)

print(f"\nSalvando em: {output_path}")

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(dados_finais, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"✅ Concluído!")
print(f"   Membros da guild: {dados_finais['total_members']}")
print(f"   Ontem: {len(dados_finais['rankings']['yesterday'])} jogadores")
print(f"   7 dias: {len(dados_finais['rankings']['7days'])} jogadores")
print(f"   30 dias: {len(dados_finais['rankings']['30days'])} jogadores")
```

if **name** == “**main**”:
main()
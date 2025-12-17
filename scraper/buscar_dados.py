#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
import time
import urllib.parse

GUILD_NAME = "Diehard"
WORLD = "Luminera"

# URL do ranking (op=3) no formato que o GuildStats realmente usa
GUILDSTATS_URL = f"https://guildstats.eu/guild%3D{urllib.parse.quote(GUILD_NAME)}%26op%3D3"

def parse_exp_value(exp_str):
    """Converte string de XP para inteiro."""
    if not exp_str or exp_str.strip() in ['*-*', '-', '', '0']:
        return 0
    clean = exp_str.strip().replace(',', '').replace('.', '').replace('+', '').replace(' ', '')
    is_negative = clean.startswith('-')
    clean = clean.replace('-', '')
    try:
        return -int(clean) if is_negative else int(clean)
    except:
        return 0

def buscar_char_info(name):
    """Busca vocação, rank, exp e outros dados da página do char no GuildStats (tab=9)."""
    url = f"https://guildstats.eu/character?nick={name}&tab=9"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        info = {'vocation': '', 'rank': '', 'exp': 0}

        rows = soup.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 2:
                continue
            key = cols[0].text.strip().lower()
            val = cols[1].text.strip()
            if key == 'vocation':
                info['vocation'] = val
            elif key == 'rank':
                info['rank'] = val
            elif key == 'experience':
                info['exp'] = parse_exp_value(val)

        return info
    except Exception as e:
        print(f"Erro buscando info do char {name}: {e}")
        return {'vocation': '', 'rank': '', 'exp': 0}

def carregar_extras():
    """Carrega lista de extras do arquivo extras.json."""
    extras_file = "extras.json"
    if os.path.exists(extras_file):
        try:
            with open(extras_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            return data.get("extras", [])
        except Exception as e:
            print(f"Erro lendo extras.json: {e}")
            return []
    return []

def salvar_dados(dados):
    """Salva dados em arquivo JSON com timestamp."""
    output_file = "dados_guild.json"
    dados_out = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "guild": GUILD_NAME,
        "world": WORLD,
        "players": dados
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(dados_out, f, ensure_ascii=False, indent=2)
    print(f"✅ Dados salvos em {output_file}")

def buscar_dados_guild():
    """Busca dados de XP da guild no GuildStats (página op=3)."""
    print(f"Buscando dados de XP do GuildStats...")
    print(f"  URL: {GUILDSTATS_URL}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    resp = requests.get(GUILDSTATS_URL, headers=headers, timeout=30)
    # Debug rápido: se a página não contiver links de personagens, provavelmente não é a tabela do ranking
    if "character?nick=" not in resp.text:
        print("⚠️ Atenção: a resposta não parece conter a tabela (sem 'character?nick=').")
        print("    Status:", resp.status_code)
        print("    URL final:", resp.url)
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    jogadores = []
    
    for row in soup.find_all('tr'):
        cols = row.find_all('td')
        if len(cols) < 15:
            continue
        
        char_link = None
        for c in cols:
            a = c.find('a')
            if a and 'character?nick=' in a.get('href', ''):
                char_link = a
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
            'rank': '',
            'exp': 0,
            'type': 'main'
        })
    
    print(f"✅ Encontrados {len(jogadores)} membros no ranking (op=3).")
    return jogadores

def adicionar_extras(jogadores):
    """Adiciona extras ao dataset (se não existirem), consultando dados no GuildStats char page."""
    extras = carregar_extras()
    if not extras:
        return jogadores
    
    nomes_existentes = {j['name'].lower() for j in jogadores}
    novos = []
    
    for extra in extras:
        if not extra or not isinstance(extra, str):
            continue
        
        if extra.lower() in nomes_existentes:
            continue
        
        print(f"➕ Buscando extra: {extra}")
        info = buscar_char_info(extra)
        novos.append({
            'name': extra,
            'level': 0,
            'exp_yesterday': 0,
            'exp_7days': 0,
            'exp_30days': 0,
            'vocation': info.get('vocation', ''),
            'rank': info.get('rank', ''),
            'exp': info.get('exp', 0),
            'type': 'extra'
        })
        time.sleep(0.6)
    
    if novos:
        print(f"✅ Extras adicionados: {len(novos)}")
    return jogadores + novos

def preencher_info_chars(jogadores):
    """Preenche vocation/rank/exp consultando página do char no GuildStats (tab=9)."""
    for i, j in enumerate(jogadores, start=1):
        if j.get('vocation') and j.get('rank') and j.get('exp'):
            continue
        
        print(f"[{i}/{len(jogadores)}] Buscando info do char: {j['name']}")
        info = buscar_char_info(j['name'])
        j['vocation'] = info.get('vocation', '')
        j['rank'] = info.get('rank', '')
        j['exp'] = info.get('exp', 0)
        time.sleep(0.5)
    
    return jogadores

def main():
    jogadores = buscar_dados_guild()
    jogadores = adicionar_extras(jogadores)
    jogadores = preencher_info_chars(jogadores)
    salvar_dados(jogadores)

if __name__ == "__main__":
    main()

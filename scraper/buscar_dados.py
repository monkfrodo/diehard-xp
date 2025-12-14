#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
import time
import re

GUILD_NAME = "Diehard"
WORLD = "Luminera"

GUILDSTATS_URL = f"https://guildstats.eu/guild?guild={GUILD_NAME}&op=3"

def parse_exp_value(exp_str):
    """Converte string de XP para inteiro."""
    if not exp_str or exp_str.strip() in ['*-*', '-', '', '0']:
        return 0
    clean = exp_str.strip().replace(',', '').replace('.', '').replace('+', '').replace(' ', '')
    is_negative = clean.startswith('-')
    clean = clean.replace('-', '')
    # Remove qualquer caractere não numérico
    clean = re.sub(r'[^\d]', '', clean)
    try:
        return -int(clean) if is_negative else int(clean)
    except:
        return 0

def buscar_vocacoes_guild_tibiadata():
    """Busca vocações e levels de todos os membros da guild via TibiaData API."""
    print("Buscando vocações da guild via TibiaData API...")
    vocacoes = {}
    try:
        url = f"https://api.tibiadata.com/v4/guild/{GUILD_NAME}"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if 'guild' in data and 'members' in data['guild']:
                for member in data['guild']['members']:
                    nome_lower = member.get('name', '').lower()
                    vocacoes[nome_lower] = {
                        'vocation': member.get('vocation', ''),
                        'level': member.get('level', 0)
                    }
                print(f"  ✓ {len(vocacoes)} vocações carregadas")
    except Exception as e:
        print(f"  ERRO: {e}")
    return vocacoes

def buscar_vocacao_individual(nome):
    """Busca vocação de um jogador específico (para extras)."""
    try:
        url = f"https://api.tibiadata.com/v4/character/{requests.utils.quote(nome)}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            char = data.get('character', {}).get('character', {})
            if char:
                return {
                    'vocation': char.get('vocation', ''),
                    'level': char.get('level', 0)
                }
    except Exception as e:
        print(f"    Erro TibiaData {nome}: {e}")
    return None

def buscar_exp_guildstats(nome):
    """Busca XP de um jogador na página individual do GuildStats (tab=9)."""
    try:
        url = f"https://guildstats.eu/character?nick={requests.utils.quote(nome)}&tab=9"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=15)
        
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

def buscar_dados_guild():
    """Busca dados de XP da guild no GuildStats (página op=3)."""
    print(f"Buscando dados de XP do GuildStats: {GUILDSTATS_URL}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    resp = requests.get(GUILDSTATS_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    
    print(f"  Status: {resp.status_code}, Tamanho: {len(resp.text)} bytes")
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    jogadores = []
    
    # Debug: conta tabelas
    tables = soup.find_all('table')
    print(f"  Tabelas encontradas: {len(tables)}")
    
    # Procura todas as linhas com links de personagem
    all_rows = soup.find_all('tr')
    print(f"  Total de linhas <tr>: {len(all_rows)}")
    
    for row in all_rows:
        cols = row.find_all('td')
        if len(cols) < 5:  # Reduzido para ser mais flexível
            continue
        
        # Procura link do personagem
        char_link = None
        char_col_idx = -1
        for idx, col in enumerate(cols):
            link = col.find('a')
            if link:
                href = link.get('href', '')
                if 'character' in href and 'nick=' in href:
                    char_link = link
                    char_col_idx = idx
                    break
        
        if not char_link:
            continue
        
        nome = char_link.text.strip()
        if not nome:
            continue
        
        # Tenta extrair level (geralmente próxima coluna após o nome)
        level = 0
        for col in cols:
            text = col.text.strip()
            if text.isdigit() and 8 <= int(text) <= 3000:  # Level válido
                level = int(text)
                break
        
        # Procura valores de XP nas últimas colunas
        # Tipicamente: ... | Exp yesterday | Exp 7 days | Exp 30 days | ON
        exp_yesterday = 0
        exp_7days = 0
        exp_30days = 0
        
        # Pega as últimas 5 colunas e tenta extrair XP
        last_cols = cols[-5:] if len(cols) >= 5 else cols
        exp_values = []
        
        for col in last_cols:
            text = col.text.strip()
            if text and text not in ['*-*', '-', 'ON', 'OFF']:
                val = parse_exp_value(text)
                if val != 0 or text == '0':
                    exp_values.append(val)
        
        # Se encontrou pelo menos 3 valores, assume que são yesterday, 7d, 30d
        if len(exp_values) >= 3:
            exp_yesterday = exp_values[-3] if len(exp_values) >= 3 else 0
            exp_7days = exp_values[-2] if len(exp_values) >= 2 else 0
            exp_30days = exp_values[-1] if len(exp_values) >= 1 else 0
        
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
    
    # Debug: mostra primeiros 3
    for j in jogadores[:3]:
        print(f"    - {j['name']}: lvl={j['level']}, ontem={j['exp_yesterday']}")
    
    return jogadores

def carregar_extras():
    """Carrega lista de extras do arquivo JSON."""
    possiveis_caminhos = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dados', 'extras.json'),
        os.path.join(os.getcwd(), 'dados', 'extras.json'),
        'dados/extras.json'
    ]
    
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

def main():
    print("=" * 60)
    print(f"Atualizando ranking: {GUILD_NAME}")
    print(f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
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
    
    # Pega nomes já existentes
    nomes_existentes = {j['name'].lower() for j in jogadores}
    
    if extras:
        print(f"\nProcessando {len(extras)} extras:")
        for nome in extras:
            # Pula se já existe na guild
            if nome.lower() in nomes_existentes:
                print(f"  → {nome}: já está na guild, pulando")
                continue
                
            print(f"  → {nome}")
            
            # Busca vocação
            dados = buscar_vocacao_individual(nome)
            if not dados:
                print(f"    ✗ Não encontrado no TibiaData")
                continue
            
            print(f"    Level {dados['level']}, {dados['vocation']}")
            
            # Busca XP
            exp = buscar_exp_guildstats(nome)
            time.sleep(0.5)  # Rate limiting
            
            jogadores.append({
                'name': nome,
                'level': dados['level'],
                'vocation': dados['vocation'],
                'exp_yesterday': exp['exp_yesterday'] if exp else 0,
                'exp_7days': exp['exp_7days'] if exp else 0,
                'exp_30days': exp['exp_30days'] if exp else 0,
                'is_extra': True
            })
    
    # 5. Cria rankings
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

if __name__ == "__main__":
    main()

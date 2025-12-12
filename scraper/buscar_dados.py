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
TOP_N = 50

GUILDSTATS_URL = f"https://guildstats.eu/guild={GUILD_NAME}&op=3"
DEATHS_URL = f"https://guildstats.eu/deaths?world={WORLD}"

def parse_exp_value(exp_str):
    if not exp_str or exp_str.strip() in ['*-*', '-', '', '0']:
        return 0
    clean = exp_str.strip().replace(',', '').replace('.', '').replace('+', '').replace(' ', '')
    is_negative = clean.startswith('-')
    clean = clean.replace('-', '')
    try:
        return -int(clean) if is_negative else int(clean)
    except:
        return 0

def buscar_vocacoes_guild_tibiadata():
    """Busca TODAS as vocações da guild de uma vez só."""
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
                print(f"  ✓ {len(vocacoes)} vocações carregadas da guild")
    except Exception as e:
        print(f"  ERRO ao buscar vocações da guild: {e}")
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
                return {'vocation': char.get('vocation', ''), 'level': char.get('level', 0)}
    except Exception as e:
        print(f"    Erro TibiaData {nome}: {e}")
    return None

def buscar_exp_extra_guildstats(nome):
    """Busca XP na aba Experience do GuildStats (tab=9)."""
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
        
        exp_por_data = {}
        
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    first_cell = cells[0].text.strip()
                    if re.match(r'\d{4}-\d{2}-\d{2}', first_cell):
                        exp_text = cells[1].text.strip()
                        exp_value = parse_exp_value(exp_text)
                        if exp_value != 0:
                            exp_por_data[first_cell] = exp_value
        
        if not exp_por_data:
            print(f"    {nome}: nenhum dado de XP encontrado")
            return None
        
        datas_ordenadas = sorted(exp_por_data.keys(), reverse=True)
        hoje = datetime.now().strftime('%Y-%m-%d')
        
        exp_today = exp_por_data.get(hoje, 0)
        
        # Ontem é a data mais recente que não é hoje
        exp_yesterday = 0
        for d in datas_ordenadas:
            if d != hoje:
                exp_yesterday = exp_por_data.get(d, 0)
                break
        
        exp_7days = sum(exp_por_data.get(d, 0) for d in datas_ordenadas[:7])
        exp_30days = sum(exp_por_data.get(d, 0) for d in datas_ordenadas[:30])
        
        print(f"    XP: hoje={exp_today:,}, ontem={exp_yesterday:,}, 7d={exp_7days:,}")
        return {
            'exp_today': exp_today,
            'exp_yesterday': exp_yesterday, 
            'exp_7days': exp_7days, 
            'exp_30days': exp_30days
        }
        
    except Exception as e:
        print(f"    Erro buscando XP de {nome}: {e}")
    return None

def buscar_dados_guild():
    """Busca dados de XP da guild no GuildStats."""
    print("Buscando dados de XP do GuildStats...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    resp = requests.get(GUILDSTATS_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    jogadores = []
    
    for row in soup.find_all('tr'):
        cols = row.find_all('td')
        if len(cols) < 5:
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
        col_texts = [col.text.strip() for col in cols]
        
        level = 0
        for i, text in enumerate(col_texts):
            if text.isdigit() and i > 0:
                num = int(text)
                if 1 < num < 5000:
                    level = num
                    break
        
        exp_values = []
        for text in col_texts:
            if (text.startswith('+') or text.startswith('-')) and ',' in text:
                exp_values.append(parse_exp_value(text))
        
        # Página op=3 mostra: Yesterday, 7 days, 30 days (3 valores)
        jogadores.append({
            'name': nome,
            'level': level,
            'exp_today': 0,  # Será preenchido depois para extras
            'exp_yesterday': exp_values[0] if len(exp_values) >= 1 else 0,
            'exp_7days': exp_values[1] if len(exp_values) >= 2 else 0,
            'exp_30days': exp_values[2] if len(exp_values) >= 3 else 0,
            'vocation': '',
            'is_extra': False
        })
    
    print(f"  ✓ {len(jogadores)} jogadores encontrados")
    return jogadores

def buscar_mortes_mundo():
    """Busca mortes do mundo Luminera na página geral de mortes."""
    print("\nBuscando mortes do mundo no GuildStats...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    mortes = []
    
    try:
        resp = requests.get(DEATHS_URL, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"  Erro ao buscar página de mortes: {resp.status_code}")
            return mortes
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Procura a tabela de mortes
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 5:
                    continue
                
                # Estrutura: # | Nick | Lvl | Daily exp | World
                col_texts = [col.text.strip() for col in cols]
                
                # Verifica se é do mundo Luminera
                if WORLD not in row.text:
                    continue
                
                # Pega o link do personagem
                char_link = None
                for col in cols:
                    link = col.find('a')
                    if link and 'character?nick=' in str(link.get('href', '')):
                        char_link = link
                        break
                
                if not char_link:
                    continue
                
                nome = char_link.text.strip()
                
                # Pega level - é o número na terceira coluna (índice 2), que vem em negrito
                level = 0
                if len(cols) > 2:
                    level_col = cols[2]
                    level_text = level_col.text.strip()
                    if level_text.isdigit():
                        level = int(level_text)
                
                # Pega XP perdida (valor negativo na quarta coluna)
                exp_lost = 0
                for text in col_texts:
                    if text.startswith('-') and ',' in text:
                        exp_lost = abs(parse_exp_value(text))
                        break
                
                mortes.append({
                    'name': nome,
                    'level': level,
                    'exp_lost': exp_lost
                })
        
        print(f"  ✓ {len(mortes)} mortes encontradas em {WORLD}")
        
    except Exception as e:
        print(f"  Erro ao buscar mortes: {e}")
    
    return mortes

def filtrar_mortes_guild(mortes_mundo, membros_guild, vocacoes_guild):
    """Filtra mortes que são de membros da guild."""
    print("Filtrando mortes de membros da guild...")
    
    nomes_guild = set(m.lower() for m in membros_guild)
    mortes_guild = []
    
    for morte in mortes_mundo:
        nome_lower = morte['name'].lower()
        if nome_lower in nomes_guild:
            vocation = ''
            if nome_lower in vocacoes_guild:
                vocation = vocacoes_guild[nome_lower].get('vocation', '')
            
            mortes_guild.append({
                'name': morte['name'],
                'level': morte['level'],
                'vocation': vocation,
                'exp_lost': morte['exp_lost'],
                'date': datetime.now().strftime('%d-%m-%Y')
            })
            print(f"    ✓ {morte['name']} (Lvl {morte['level']}) - {morte['exp_lost']:,} XP perdida")
    
    print(f"  ✓ {len(mortes_guild)} mortes de membros da guild")
    return mortes_guild

def carregar_extras():
    """Carrega extras tentando múltiplos caminhos."""
    possiveis_caminhos = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dados', 'extras.json'),
        os.path.join(os.getcwd(), 'dados', 'extras.json'),
        'dados/extras.json'
    ]
    
    for caminho in possiveis_caminhos:
        print(f"  Tentando: {caminho}")
        if os.path.exists(caminho):
            try:
                with open(caminho, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    extras = [e.get('nome', '') for e in data.get('extras', []) if e.get('nome')]
                    print(f"  ✓ Carregados {len(extras)} extras de {caminho}")
                    return extras
            except Exception as e:
                print(f"  Erro ao ler {caminho}: {e}")
    
    print("  ✗ Nenhum arquivo extras.json encontrado!")
    return []

def main():
    print("=" * 60)
    print(f"Atualizando ranking: {GUILD_NAME}")
    print(f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Diretório atual: {os.getcwd()}")
    print("=" * 60)
    
    # 1. Busca vocações da guild
    vocacoes_guild = buscar_vocacoes_guild_tibiadata()
    
    # 2. Busca dados de XP da guild
    jogadores = buscar_dados_guild()
    
    # 3. Aplica vocações
    print("\nAplicando vocações aos jogadores...")
    sem_vocacao = 0
    for jogador in jogadores:
        nome_lower = jogador['name'].lower()
        if nome_lower in vocacoes_guild:
            jogador['vocation'] = vocacoes_guild[nome_lower]['vocation']
            if jogador['level'] == 0:
                jogador['level'] = vocacoes_guild[nome_lower]['level']
        else:
            sem_vocacao += 1
    
    print(f"  ✓ Vocações aplicadas ({sem_vocacao} sem vocação)")
    
    # 4. Processa extras
    print("\nCarregando extras...")
    extras = carregar_extras()
    print(f"\nExtras ({len(extras)}): {extras}")
    
    for nome in extras:
        print(f"\n  Buscando: {nome}")
        
        dados = buscar_vocacao_individual(nome)
        if not dados:
            print(f"    ERRO: não encontrado")
            continue
        
        print(f"    OK: Lvl {dados['level']}, {dados['vocation']}")
        
        exp = buscar_exp_extra_guildstats(nome)
        time.sleep(0.5)
        
        jogadores.append({
            'name': nome,
            'level': dados['level'],
            'vocation': dados['vocation'],
            'exp_today': exp['exp_today'] if exp else 0,
            'exp_yesterday': exp['exp_yesterday'] if exp else 0,
            'exp_7days': exp['exp_7days'] if exp else 0,
            'exp_30days': exp['exp_30days'] if exp else 0,
            'is_extra': True
        })
        
        # Adiciona vocação do extra ao dicionário
        vocacoes_guild[nome.lower()] = {'vocation': dados['vocation'], 'level': dados['level']}
    
    # 5. Busca mortes
    nomes_membros = [j['name'] for j in jogadores]
    mortes_mundo = buscar_mortes_mundo()
    mortes_guild = filtrar_mortes_guild(mortes_mundo, nomes_membros, vocacoes_guild)
    
    # 6. Cria rankings
    def criar_ranking(jogadores, campo, top_n):
        filtrados = [j for j in jogadores if j.get(campo, 0) > 0]
        filtrados.sort(key=lambda x: x.get(campo, 0), reverse=True)
        return [{'rank': i, 'name': j['name'], 'vocation': j['vocation'], 'level': j['level'], 
                 'points': j[campo], 'is_extra': j.get('is_extra', False)} 
                for i, j in enumerate(filtrados[:top_n], 1)]
    
    dados_finais = {
        'guild': GUILD_NAME,
        'world': WORLD,
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'last_update_display': datetime.now().strftime('%d/%m/%Y às %H:%M'),
        'total_members': len([j for j in jogadores if not j.get('is_extra')]),
        'rankings': {
            'today': criar_ranking(jogadores, 'exp_today', TOP_N),
            'yesterday': criar_ranking(jogadores, 'exp_yesterday', TOP_N),
            '7days': criar_ranking(jogadores, 'exp_7days', TOP_N),
            '30days': criar_ranking(jogadores, 'exp_30days', TOP_N)
        },
        'deaths': mortes_guild
    }
    
    # Salva o arquivo
    output_path = os.path.join(os.getcwd(), 'dados', 'ranking.json')
    print(f"\nSalvando em: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dados_finais, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ Concluído!")
    print(f"   Hoje: {len(dados_finais['rankings']['today'])} jogadores")
    print(f"   Ontem: {len(dados_finais['rankings']['yesterday'])} jogadores")
    print(f"   7 dias: {len(dados_finais['rankings']['7days'])} jogadores")  
    print(f"   30 dias: {len(dados_finais['rankings']['30days'])} jogadores")
    print(f"   Mortes: {len(dados_finais['deaths'])} registros")

if __name__ == "__main__":
    main()

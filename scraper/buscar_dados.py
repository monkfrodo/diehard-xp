#!/usr/bin/env python3
"""
Script para buscar dados de XP da guild Diehard no GuildStats.eu
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
import time

# Configurações
GUILD_NAME = "Diehard"
WORLD = "Luminera"
TOP_N = 50

GUILDSTATS_URL = f"https://guildstats.eu/guild={GUILD_NAME}&op=3"

def parse_exp_value(exp_str):
    """Converte string de XP para número inteiro."""
    if not exp_str or exp_str.strip() in ['*-*', '-', '', '0']:
        return 0
    clean = exp_str.strip().replace(',', '').replace('.', '').replace('+', '').replace(' ', '')
    is_negative = clean.startswith('-')
    clean = clean.replace('-', '')
    try:
        value = int(clean)
        return -value if is_negative else value
    except ValueError:
        return 0

def buscar_vocacao_tibiadata(nome):
    """Busca vocação de um jogador via TibiaData API."""
    try:
        url = f"https://api.tibiadata.com/v4/character/{requests.utils.quote(nome)}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'character' in data and 'character' in data['character']:
                char = data['character']['character']
                return {
                    'vocation': char.get('vocation', ''),
                    'level': char.get('level', 0),
                    'world': char.get('world', '')
                }
    except Exception as e:
        print(f"    Erro TibiaData para {nome}: {e}")
    return None

def buscar_exp_jogador_guildstats(nome):
    """Busca XP de um jogador específico no GuildStats."""
    try:
        url = f"https://guildstats.eu/character?nick={requests.utils.quote(nome)}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Procura valores de XP na página (formato +XXX,XXX ou -XXX,XXX)
        exp_values = []
        for text in soup.get_text().split():
            if (text.startswith('+') or text.startswith('-')) and ',' in text:
                val = parse_exp_value(text)
                if val != 0:
                    exp_values.append(val)
        
        # Também procura em tabelas
        for row in soup.find_all('tr'):
            for cell in row.find_all('td'):
                text = cell.text.strip()
                if (text.startswith('+') or text.startswith('-')) and ',' in text:
                    val = parse_exp_value(text)
                    if val != 0 and val not in exp_values:
                        exp_values.append(val)
        
        if exp_values:
            # Ordena para pegar os maiores valores (provavelmente 30d, 7d, yesterday)
            exp_values_sorted = sorted([abs(v) for v in exp_values], reverse=True)
            return {
                'exp_30days': exp_values_sorted[0] if len(exp_values_sorted) > 0 else 0,
                'exp_7days': exp_values_sorted[1] if len(exp_values_sorted) > 1 else 0,
                'exp_yesterday': exp_values_sorted[2] if len(exp_values_sorted) > 2 else 0
            }
    except Exception as e:
        print(f"    Erro GuildStats para {nome}: {e}")
    return None

def buscar_dados_guildstats():
    """Faz scraping do GuildStats."""
    print(f"Buscando dados do GuildStats...")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    response = requests.get(GUILDSTATS_URL, headers=headers, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
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
            if text.isdigit():
                num = int(text)
                if 1 < num < 5000 and i > 0:
                    level = num
                    break
        
        exp_values = []
        for text in col_texts:
            if (text.startswith('+') or text.startswith('-')) and ',' in text:
                exp_values.append(parse_exp_value(text))
            elif text == '0':
                exp_values.append(0)
        
        exp_yesterday = exp_values[0] if len(exp_values) > 0 else 0
        exp_7days = exp_values[1] if len(exp_values) > 1 else 0
        exp_30days = exp_values[2] if len(exp_values) > 2 else 0
        
        jogadores.append({
            'name': nome,
            'level': level,
            'exp_yesterday': exp_yesterday,
            'exp_7days': exp_7days,
            'exp_30days': exp_30days,
            'vocation': '',
            'is_extra': False
        })
    
    print(f"  Encontrados {len(jogadores)} jogadores da guild")
    return jogadores

def carregar_extras():
    """Carrega jogadores extras do arquivo."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    extras_path = os.path.join(script_dir, '..', 'dados', 'extras.json')
    
    print(f"  Procurando extras em: {extras_path}")
    
    if os.path.exists(extras_path):
        try:
            with open(extras_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                extras = [e.get('nome', '') for e in data.get('extras', []) if e.get('nome')]
                print(f"  Extras encontrados: {extras}")
                return extras
        except Exception as e:
            print(f"  Erro ao carregar extras: {e}")
    else:
        print(f"  Arquivo extras.json não encontrado")
    return []

def main():
    print("=" * 60)
    print(f"Atualizando ranking da guild {GUILD_NAME}")
    print(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. Busca dados da guild
    jogadores = buscar_dados_guildstats()
    
    # 2. Carrega e processa jogadores extras
    nomes_extras = carregar_extras()
    
    if nomes_extras:
        print(f"\nProcessando {len(nomes_extras)} jogadores extras...")
        for nome in nomes_extras:
            print(f"  Buscando: {nome}")
            
            # Busca dados do TibiaData
            tibia_data = buscar_vocacao_tibiadata(nome)
            if not tibia_data:
                print(f"    {nome}: não encontrado no TibiaData")
                continue
            
            # Busca XP no GuildStats
            exp_data = buscar_exp_jogador_guildstats(nome)
            
            jogador = {
                'name': tibia_data.get('name', nome) if 'name' in tibia_data else nome,
                'level': tibia_data.get('level', 0),
                'vocation': tibia_data.get('vocation', ''),
                'exp_yesterday': exp_data.get('exp_yesterday', 0) if exp_data else 0,
                'exp_7days': exp_data.get('exp_7days', 0) if exp_data else 0,
                'exp_30days': exp_data.get('exp_30days', 0) if exp_data else 0,
                'is_extra': True
            }
            
            jogadores.append(jogador)
            print(f"    {nome}: Lvl {jogador['level']}, Voc: {jogador['vocation']}, XP 7d: {jogador['exp_7days']:,}")
            
            time.sleep(0.5)
    
    # 3. Busca vocações faltantes
    print("\nBuscando vocações faltantes...")
    for jogador in jogadores:
        if not jogador.get('vocation'):
            tibia_data = buscar_vocacao_tibiadata(jogador['name'])
            if tibia_data:
                jogador['vocation'] = tibia_data.get('vocation', '')
                if jogador.get('level', 0) == 0:
                    jogador['level'] = tibia_data.get('level', 0)
            time.sleep(0.2)
    
    # 4. Cria rankings
    def criar_ranking(jogadores, campo_exp, top_n):
        filtrados = [j for j in jogadores if j.get(campo_exp, 0) > 0]
        filtrados.sort(key=lambda x: x.get(campo_exp, 0), reverse=True)
        resultado = []
        for i, j in enumerate(filtrados[:top_n], 1):
            resultado.append({
                'rank': i,
                'name': j['name'],
                'vocation': j.get('vocation', ''),
                'level': j.get('level', 0),
                'points': j.get(campo_exp, 0),
                'is_extra': j.get('is_extra', False)
            })
        return resultado
    
    ranking_yesterday = criar_ranking(jogadores, 'exp_yesterday', TOP_N)
    ranking_7days = criar_ranking(jogadores, 'exp_7days', TOP_N)
    ranking_30days = criar_ranking(jogadores, 'exp_30days', TOP_N)
    
    # 5. Salva
    dados_finais = {
        'guild': GUILD_NAME,
        'world': WORLD,
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'last_update_display': datetime.now().strftime('%d/%m/%Y às %H:%M'),
        'total_members': len([j for j in jogadores if not j.get('is_extra')]),
        'rankings': {
            'yesterday': ranking_yesterday,
            '7days': ranking_7days,
            '30days': ranking_30days
        }
    }
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, '..', 'dados', 'ranking.json')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dados_finais, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ Ranking atualizado!")
    print(f"   Ontem: {len(ranking_yesterday)} | 7 dias: {len(ranking_7days)} | 30 dias: {len(ranking_30days)}")
    print(f"{'='*60}")
    
    # Preview dos extras no ranking
    extras_no_ranking = [j for j in ranking_7days if j.get('is_extra')]
    if extras_no_ranking:
        print(f"\n--- Jogadores EXTRAS no ranking 7 dias ---")
        for j in extras_no_ranking[:10]:
            print(f"#{j['rank']:2} {j['name']:<25} {j['points']:>15,}")

if __name__ == "__main__":
    main()

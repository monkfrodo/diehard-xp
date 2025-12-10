#!/usr/bin/env python3
"""
Script para buscar dados de XP da guild Diehard no GuildStats.eu
Coleta: XP de ontem, XP 7 dias, XP 30 dias
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
import re
import time

# Configurações
GUILD_NAME = "Diehard"
WORLD = "Luminera"
TOP_N = 50  # Pega mais para ter dados suficientes

# URLs
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
    except:
        pass
    return None

def buscar_dados_guildstats():
    """Faz scraping do GuildStats."""
    print(f"Buscando dados do GuildStats...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    response = requests.get(GUILDSTATS_URL, headers=headers, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    jogadores = []
    
    for row in soup.find_all('tr'):
        cols = row.find_all('td')
        if len(cols) < 5:
            continue
        
        # Procura link do personagem
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
        
        # Encontra o level
        level = 0
        for i, text in enumerate(col_texts):
            if text.isdigit():
                num = int(text)
                if 1 < num < 5000 and i > 0:
                    level = num
                    break
        
        # Encontra valores de XP
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
            'vocation': ''
        })
    
    print(f"  Encontrados {len(jogadores)} jogadores da guild")
    return jogadores

def carregar_extras():
    """Carrega jogadores extras do arquivo."""
    extras_path = os.path.join(os.path.dirname(__file__), '..', 'dados', 'extras.json')
    
    if os.path.exists(extras_path):
        try:
            with open(extras_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [e.get('nome', '') for e in data.get('extras', []) if e.get('nome')]
        except:
            pass
    return []

def buscar_dados_extras_guildstats(nomes):
    """Busca dados de XP dos jogadores extras no GuildStats."""
    print(f"Buscando dados de {len(nomes)} jogadores extras...")
    
    extras = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for nome in nomes:
        try:
            # Busca página do jogador no GuildStats
            url = f"https://guildstats.eu/character?nick={requests.utils.quote(nome)}"
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                print(f"  {nome}: não encontrado no GuildStats")
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Procura dados de XP na página
            exp_yesterday = 0
            exp_7days = 0
            exp_30days = 0
            level = 0
            
            # Procura na tabela de experiência
            for row in soup.find_all('tr'):
                cols = row.find_all('td')
                col_texts = [col.text.strip() for col in cols]
                
                # Procura valores de XP
                for text in col_texts:
                    if (text.startswith('+') or text.startswith('-')) and ',' in text:
                        val = parse_exp_value(text)
                        if exp_yesterday == 0:
                            exp_yesterday = val
                        elif exp_7days == 0:
                            exp_7days = val
                        elif exp_30days == 0:
                            exp_30days = val
            
            # Busca level e vocação via TibiaData
            tibia_data = buscar_vocacao_tibiadata(nome)
            if tibia_data:
                level = tibia_data.get('level', 0)
                vocation = tibia_data.get('vocation', '')
            else:
                vocation = ''
            
            extras.append({
                'name': nome,
                'level': level,
                'exp_yesterday': exp_yesterday,
                'exp_7days': exp_7days,
                'exp_30days': exp_30days,
                'vocation': vocation,
                'is_extra': True
            })
            
            print(f"  {nome}: Lvl {level}, XP ontem: {exp_yesterday:,}")
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"  {nome}: erro - {e}")
    
    return extras

def main():
    print("=" * 60)
    print(f"Atualizando ranking da guild {GUILD_NAME}")
    print(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. Busca dados da guild no GuildStats
    jogadores = buscar_dados_guildstats()
    
    # 2. Carrega e busca jogadores extras
    nomes_extras = carregar_extras()
    if nomes_extras:
        extras = buscar_dados_extras_guildstats(nomes_extras)
        jogadores.extend(extras)
    
    # 3. Busca vocações faltantes via TibiaData
    print("\nBuscando vocações via TibiaData...")
    for i, jogador in enumerate(jogadores):
        if not jogador.get('vocation'):
            tibia_data = buscar_vocacao_tibiadata(jogador['name'])
            if tibia_data:
                jogador['vocation'] = tibia_data.get('vocation', '')
                if jogador.get('level', 0) == 0:
                    jogador['level'] = tibia_data.get('level', 0)
            
            # Rate limiting - busca em lotes
            if (i + 1) % 10 == 0:
                print(f"  Processados {i + 1}/{len(jogadores)}...")
                time.sleep(1)
    
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
    
    output_path = os.path.join(os.path.dirname(__file__), '..', 'dados', 'ranking.json')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dados_finais, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ Ranking atualizado!")
    print(f"   Ontem: {len(ranking_yesterday)} | 7 dias: {len(ranking_7days)} | 30 dias: {len(ranking_30days)}")
    print(f"{'='*60}")
    
    if ranking_yesterday:
        print("\n--- Top 5 XP Ontem ---")
        for j in ranking_yesterday[:5]:
            extra = " ⭐" if j.get('is_extra') else ""
            print(f"#{j['rank']:2} {j['name']:<25} {j['points']:>15,}{extra}")

if __name__ == "__main__":
    main()

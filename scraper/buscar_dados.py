#!/usr/bin/env python3
"""
Scraper de XP para Guild Diehard - Luminera
Versão 2.0 - Corrigida e testada

CORREÇÕES:
- Parsing de XP usa índice fixo (13, 14, 15) em vez de negativo
- Level extraído da coluna correta (índice 2)
- Membros da guild vêm do TibiaData (fonte confiável)
- Extras são filtrados automaticamente (remove quem já está na guild)
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
import time
import re
import sys
import traceback

# Configurações
GUILD_NAME = "Diehard"
WORLD = "Luminera"
DEBUG = True

# URLs
GUILDSTATS_URL = f"https://guildstats.eu/guild?guild={GUILD_NAME}&op=3"
TIBIADATA_GUILD_URL = f"https://api.tibiadata.com/v4/guild/{GUILD_NAME}"

def log(msg, level="INFO"):
    """Log com timestamp e emoji."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    prefix = {
        "INFO": "ℹ️", 
        "OK": "✅", 
        "WARN": "⚠️", 
        "ERROR": "❌", 
        "DEBUG": "🔍"
    }.get(level, "")
    print(f"[{timestamp}] {prefix} {msg}")
    sys.stdout.flush()

def parse_exp_value(exp_str):
    """
    Converte string de XP para inteiro.
    Exemplos: "+27,260,559" -> 27260559, "*-*" -> 0, "-5,374,547" -> -5374547
    """
    if not exp_str:
        return 0
    
    clean = exp_str.strip()
    
    # Valores que indicam ausência de dados
    if clean in ['*-*', '-', '', '0', '*']:
        return 0
    
    # Verifica se é negativo (começa com - seguido de dígito)
    is_negative = bool(re.match(r'^-[\d,.]', clean))
    
    # Remove tudo exceto dígitos
    digits_only = re.sub(r'[^\d]', '', clean)
    
    if not digits_only:
        return 0
    
    try:
        value = int(digits_only)
        return -value if is_negative else value
    except ValueError:
        return 0

def buscar_membros_tibiadata():
    """
    Busca lista COMPLETA de membros da guild via TibiaData API.
    Retorna dict com nome_lower -> {name, vocation, level}
    """
    log("Buscando membros da guild via TibiaData API...")
    
    try:
        headers = {'User-Agent': 'Diehard-XP-Tracker/2.0'}
        resp = requests.get(TIBIADATA_GUILD_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        
        data = resp.json()
        
        if 'guild' not in data or 'members' not in data['guild']:
            log("Resposta inválida da TibiaData", "ERROR")
            return {}
        
        membros = {}
        for member in data['guild']['members']:
            nome = member.get('name', '')
            if nome:
                membros[nome.lower()] = {
                    'name': nome,
                    'vocation': member.get('vocation', ''),
                    'level': member.get('level', 0)
                }
        
        log(f"Encontrados {len(membros)} membros na guild", "OK")
        return membros
        
    except Exception as e:
        log(f"Erro ao buscar TibiaData: {e}", "ERROR")
        if DEBUG:
            traceback.print_exc()
        return {}

def buscar_xp_guildstats():
    """
    Busca dados de XP da página do GuildStats.
    Retorna dict com nome_lower -> {name, level, exp_yesterday, exp_7days, exp_30days}
    
    ESTRUTURA DA TABELA (16-17 colunas):
    0: #, 1: Nick, 2: Lvl, 3-12: tempos, 13: Exp yesterday, 14: Exp 7 days, 15: Exp 30 days, 16: ON
    """
    log(f"Buscando XP do GuildStats...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        resp = requests.get(GUILDSTATS_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        
        # Salva HTML para debug
        debug_dir = os.path.join(os.getcwd(), 'dados')
        os.makedirs(debug_dir, exist_ok=True)
        debug_path = os.path.join(debug_dir, 'debug_guildstats.html')
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(resp.text)
        log(f"HTML salvo em {debug_path}", "DEBUG")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        tables = soup.find_all('table')
        log(f"Encontradas {len(tables)} tabelas", "DEBUG")
        
        dados_xp = {}
        tabela_encontrada = False
        
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 10:
                continue
            
            # Verifica se é a tabela de XP
            header = rows[0].get_text().lower() if rows else ""
            if 'exp' not in header and 'yesterday' not in header:
                continue
            
            tabela_encontrada = True
            log(f"Tabela de XP encontrada com {len(rows)} linhas", "OK")
            
            for i, row in enumerate(rows[1:], 1):  # Pula header
                cells = row.find_all('td')
                
                if len(cells) < 14:  # Precisa de pelo menos 14 colunas
                    continue
                
                # Extrai dados usando ÍNDICES FIXOS
                # Coluna 1: Nome (com link)
                nome = None
                nome_cell = cells[1] if len(cells) > 1 else None
                if nome_cell:
                    link = nome_cell.find('a')
                    nome = link.get_text().strip() if link else nome_cell.get_text().strip()
                
                if not nome:
                    continue
                
                # Coluna 2: Level
                level = 0
                level_cell = cells[2] if len(cells) > 2 else None
                if level_cell:
                    level_text = level_cell.get_text().strip()
                    if level_text.isdigit():
                        level = int(level_text)
                
                # Colunas 13, 14, 15: XP (ÍNDICES FIXOS!)
                exp_yesterday = parse_exp_value(cells[13].get_text()) if len(cells) > 13 else 0
                exp_7days = parse_exp_value(cells[14].get_text()) if len(cells) > 14 else 0
                exp_30days = parse_exp_value(cells[15].get_text()) if len(cells) > 15 else 0
                
                dados_xp[nome.lower()] = {
                    'name': nome,
                    'level': level,
                    'exp_yesterday': exp_yesterday,
                    'exp_7days': exp_7days,
                    'exp_30days': exp_30days
                }
                
                # Debug das primeiras linhas
                if DEBUG and i <= 3:
                    log(f"  {nome}: Lvl {level}, Y={exp_yesterday:,}, 7D={exp_7days:,}, 30D={exp_30days:,}", "DEBUG")
            
            break  # Encontrou a tabela certa
        
        if not tabela_encontrada:
            log("Tabela de XP não encontrada no HTML!", "ERROR")
            return {}
        
        log(f"XP extraída para {len(dados_xp)} jogadores", "OK")
        return dados_xp
        
    except Exception as e:
        log(f"Erro ao buscar GuildStats: {e}", "ERROR")
        if DEBUG:
            traceback.print_exc()
        return {}

def buscar_vocacao_individual(nome):
    """Busca vocação de um jogador específico via TibiaData."""
    try:
        import urllib.parse
        url = f"https://api.tibiadata.com/v4/character/{urllib.parse.quote(nome)}"
        headers = {'User-Agent': 'Diehard-XP-Tracker/2.0'}
        
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            char = data.get('character', {}).get('character', {})
            if char and char.get('name'):
                return {
                    'vocation': char.get('vocation', ''),
                    'level': char.get('level', 0)
                }
        return None
    except:
        return None

def buscar_xp_individual(nome):
    """Busca XP de um jogador na página individual do GuildStats."""
    try:
        import urllib.parse
        url = f"https://guildstats.eu/character?nick={urllib.parse.quote(nome)}&tab=9"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        
        if "does not exsists" in resp.text or "don't have in our datebase" in resp.text:
            return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        exp_values = []
        
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    date_cell = cells[0].get_text().strip()
                    exp_cell = cells[1].get_text().strip()
                    
                    if re.match(r'\d{4}-\d{2}-\d{2}', date_cell):
                        exp_values.append(parse_exp_value(exp_cell))
        
        if not exp_values:
            return None
        
        return {
            'exp_yesterday': exp_values[-1] if len(exp_values) >= 1 else 0,
            'exp_7days': sum(exp_values[-7:]) if exp_values else 0,
            'exp_30days': sum(exp_values[-30:]) if exp_values else 0
        }
    except:
        return None

def carregar_extras():
    """Carrega lista de extras do arquivo JSON."""
    caminhos = [
        os.path.join(os.getcwd(), 'dados', 'extras.json'),
        'dados/extras.json',
    ]
    
    for caminho in caminhos:
        if os.path.exists(caminho):
            try:
                with open(caminho, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    extras = [e.get('nome', '') for e in data.get('extras', []) if e.get('nome')]
                    log(f"{len(extras)} extras no arquivo", "OK")
                    return extras
            except Exception as e:
                log(f"Erro ao ler {caminho}: {e}", "WARN")
    
    return []

def main():
    """Função principal."""
    print("=" * 70)
    log(f"INICIANDO ATUALIZAÇÃO DO RANKING - {GUILD_NAME}")
    log(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    output_dir = os.path.join(os.getcwd(), 'dados')
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Busca membros da guild (TibiaData = fonte confiável para vocações/levels)
    membros_guild = buscar_membros_tibiadata()
    
    # 2. Busca XP do GuildStats
    dados_xp = buscar_xp_guildstats()
    
    if not dados_xp and not membros_guild:
        log("ERRO CRÍTICO: Não foi possível obter dados de nenhuma fonte!", "ERROR")
        error_log = {
            'timestamp': datetime.now().isoformat(),
            'error': 'Falha ao buscar dados do GuildStats e TibiaData'
        }
        with open(os.path.join(output_dir, 'error_log.json'), 'w') as f:
            json.dump(error_log, f, indent=2)
        sys.exit(1)
    
    # 3. Combina dados: XP do GuildStats + Vocações do TibiaData
    log("Combinando dados...")
    jogadores = []
    nomes_processados = set()
    
    # Processa jogadores que têm XP no GuildStats
    for nome_lower, xp in dados_xp.items():
        jogador = {
            'name': xp['name'],
            'level': xp['level'],
            'vocation': '',
            'exp_yesterday': xp['exp_yesterday'],
            'exp_7days': xp['exp_7days'],
            'exp_30days': xp['exp_30days'],
            'is_extra': nome_lower not in membros_guild
        }
        
        # Complementa com dados do TibiaData
        if nome_lower in membros_guild:
            jogador['vocation'] = membros_guild[nome_lower]['vocation']
            # Usa o level maior (TibiaData é mais atualizado)
            if membros_guild[nome_lower]['level'] > jogador['level']:
                jogador['level'] = membros_guild[nome_lower]['level']
        
        jogadores.append(jogador)
        nomes_processados.add(nome_lower)
    
    # Adiciona membros da guild que não apareceram no GuildStats (sem XP recente)
    for nome_lower, membro in membros_guild.items():
        if nome_lower not in nomes_processados:
            jogadores.append({
                'name': membro['name'],
                'level': membro['level'],
                'vocation': membro['vocation'],
                'exp_yesterday': 0,
                'exp_7days': 0,
                'exp_30days': 0,
                'is_extra': False
            })
            nomes_processados.add(nome_lower)
    
    total_guild = len([j for j in jogadores if not j['is_extra']])
    log(f"Total membros da guild: {total_guild}", "OK")
    
    # 4. Processa extras (apenas quem NÃO está na guild)
    extras_arquivo = carregar_extras()
    
    if extras_arquivo:
        # Filtra: só processa quem NÃO está na guild
        extras_reais = [e for e in extras_arquivo if e.lower() not in nomes_processados]
        
        if extras_reais:
            log(f"Processando {len(extras_reais)} extras (de {len(extras_arquivo)} no arquivo)...")
            
            for i, nome in enumerate(extras_reais):
                if i > 0 and i % 5 == 0:
                    time.sleep(2)
                elif i > 0:
                    time.sleep(0.5)
                
                log(f"  → {nome} ({i+1}/{len(extras_reais)})")
                
                # Busca vocação
                voc = buscar_vocacao_individual(nome)
                if not voc:
                    log(f"    Não encontrado", "WARN")
                    continue
                
                # Busca XP
                xp = buscar_xp_individual(nome)
                time.sleep(0.5)
                
                jogadores.append({
                    'name': nome,
                    'level': voc['level'],
                    'vocation': voc['vocation'],
                    'exp_yesterday': xp['exp_yesterday'] if xp else 0,
                    'exp_7days': xp['exp_7days'] if xp else 0,
                    'exp_30days': xp['exp_30days'] if xp else 0,
                    'is_extra': True
                })
                nomes_processados.add(nome.lower())
        else:
            log("Todos os extras já estão na guild ou já processados", "INFO")
    
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
        'total_members': total_guild,
        'total_extras': len([j for j in jogadores if j.get('is_extra')]),
        'rankings': {
            'yesterday': criar_ranking(jogadores, 'exp_yesterday'),
            '7days': criar_ranking(jogadores, 'exp_7days'),
            '30days': criar_ranking(jogadores, 'exp_30days')
        }
    }
    
    # 6. Salva
    output_path = os.path.join(output_dir, 'ranking.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dados_finais, f, ensure_ascii=False, indent=2)
    
    log(f"Ranking salvo em {output_path}", "OK")
    
    # 7. Gera arquivo de STATUS para validação
    # Pega top 5 de ontem como amostra
    top5_ontem = dados_finais['rankings']['yesterday'][:5]
    amostra = []
    for p in top5_ontem:
        amostra.append({
            'pos': p['rank'],
            'nome': p['name'],
            'xp': f"{p['points']:,}".replace(',', '.')
        })
    
    status = {
        'ultima_execucao': datetime.now().strftime('%d/%m/%Y às %H:%M:%S'),
        'sucesso': True,
        'fonte_membros': 'TibiaData API',
        'fonte_xp': 'GuildStats.eu',
        'total_membros_guild': dados_finais['total_members'],
        'total_extras': dados_finais['total_extras'],
        'jogadores_com_xp_ontem': len(dados_finais['rankings']['yesterday']),
        'jogadores_com_xp_7dias': len(dados_finais['rankings']['7days']),
        'jogadores_com_xp_30dias': len(dados_finais['rankings']['30days']),
        'top5_ontem': amostra,
        'validacao': {
            'tem_dados': len(dados_finais['rankings']['yesterday']) > 0,
            'xp_parece_correta': top5_ontem[0]['points'] > 1000000 if top5_ontem else False,
            'msg': '✅ Tudo OK!' if (len(dados_finais['rankings']['yesterday']) > 0 and (top5_ontem[0]['points'] > 1000000 if top5_ontem else False)) else '⚠️ Verificar dados'
        }
    }
    
    status_path = os.path.join(output_dir, 'status.json')
    with open(status_path, 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    
    log(f"Status salvo em {status_path}", "OK")
    
    # 8. Resumo
    print("\n" + "=" * 70)
    log("ATUALIZAÇÃO CONCLUÍDA!")
    log(f"  Membros da guild: {dados_finais['total_members']}")
    log(f"  Extras: {dados_finais['total_extras']}")
    log(f"  Ranking Ontem: {len(dados_finais['rankings']['yesterday'])} com XP > 0")
    log(f"  Ranking 7 dias: {len(dados_finais['rankings']['7days'])} com XP > 0")
    log(f"  Ranking 30 dias: {len(dados_finais['rankings']['30days'])} com XP > 0")
    log(f"  {status['validacao']['msg']}")
    print("=" * 70)

if __name__ == "__main__":
    main()

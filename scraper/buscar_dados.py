#!/usr/bin/env python3
"""
Scraper de XP para Guild Diehard - Luminera
Versão 2.2 - Com retry automático até GuildStats atualizar

FUNCIONALIDADES:
- Tenta buscar dados a cada 5 minutos até GuildStats atualizar
- Máximo de 36 tentativas (3 horas)
- Mostra status na página enquanto não atualiza
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

# Retry config
MAX_TENTATIVAS = 36  # 36 x 5min = 3 horas
INTERVALO_RETRY = 5 * 60  # 5 minutos em segundos
MIN_MEMBROS_COM_XP = 10  # Mínimo de membros com XP pra considerar "atualizado"

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
        "DEBUG": "🔍",
        "RETRY": "🔄"
    }.get(level, "")
    print(f"[{timestamp}] {prefix} {msg}")
    sys.stdout.flush()

def parse_exp_value(exp_str):
    if not exp_str:
        return 0
    clean = exp_str.strip()
    if clean in ['*-*', '-', '', '0', '*']:
        return 0
    is_negative = bool(re.match(r'^-[\d,.]', clean))
    digits_only = re.sub(r'[^\d]', '', clean)
    if not digits_only:
        return 0
    try:
        value = int(digits_only)
        return -value if is_negative else value
    except ValueError:
        return 0

def buscar_membros_tibiadata():
    log("Buscando membros da guild via TibiaData API...")
    try:
        headers = {'User-Agent': 'Diehard-XP-Tracker/2.2'}
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
        return {}

def buscar_xp_guildstats():
    """
    Busca dados de XP do GuildStats.
    Retorna tuple: (dados_xp dict, total_membros_com_xp_ontem int)
    """
    log(f"Buscando XP do GuildStats...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
        }
        
        resp = requests.get(GUILDSTATS_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        
        # Salva HTML para debug
        debug_dir = os.path.join(os.getcwd(), 'dados')
        os.makedirs(debug_dir, exist_ok=True)
        with open(os.path.join(debug_dir, 'debug_guildstats.html'), 'w', encoding='utf-8') as f:
            f.write(resp.text)
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        tables = soup.find_all('table')
        
        dados_xp = {}
        melhor_tabela = None
        max_rows = 0
        
        for table in tables:
            rows = table.find_all('tr')
            has_char_links = any('character?nick=' in str(row) for row in rows[:5])
            if has_char_links and len(rows) > max_rows:
                max_rows = len(rows)
                melhor_tabela = table
        
        if not melhor_tabela:
            log("Tabela não encontrada!", "ERROR")
            return {}, 0
        
        rows = melhor_tabela.find_all('tr')
        total_membros_com_xp_ontem = 0
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 14:
                continue
            
            nome = None
            for cell in cells[:3]:
                link = cell.find('a', href=lambda h: h and 'character?nick=' in h)
                if link:
                    nome = link.get_text().strip()
                    break
            
            if not nome:
                continue
            
            level = 0
            for cell in cells[2:5]:
                text = cell.get_text().strip()
                if text.isdigit() and 8 <= int(text) <= 9999:
                    level = int(text)
                    break
            
            exp_yesterday = parse_exp_value(cells[13].get_text()) if len(cells) > 13 else 0
            exp_7days = parse_exp_value(cells[14].get_text()) if len(cells) > 14 else 0
            exp_30days = parse_exp_value(cells[15].get_text()) if len(cells) > 15 else 0
            
            # Conta XP positiva (não conta quem morreu/perdeu XP)
            if exp_yesterday > 0:
                total_membros_com_xp_ontem += 1
            
            dados_xp[nome.lower()] = {
                'name': nome,
                'level': level,
                'exp_yesterday': exp_yesterday,
                'exp_7days': exp_7days,
                'exp_30days': exp_30days
            }
        
        log(f"XP extraída: {len(dados_xp)} jogadores, {total_membros_com_xp_ontem} com XP ontem", "OK")
        return dados_xp, total_membros_com_xp_ontem
        
    except Exception as e:
        log(f"Erro ao buscar GuildStats: {e}", "ERROR")
        return {}, 0

def buscar_vocacao_individual(nome):
    try:
        import urllib.parse
        url = f"https://api.tibiadata.com/v4/character/{urllib.parse.quote(nome)}"
        resp = requests.get(url, headers={'User-Agent': 'Diehard-XP-Tracker/2.2'}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            char = data.get('character', {}).get('character', {})
            if char and char.get('name'):
                return {'vocation': char.get('vocation', ''), 'level': char.get('level', 0)}
        return None
    except:
        return None

def buscar_xp_individual(nome):
    try:
        import urllib.parse
        url = f"https://guildstats.eu/character?nick={urllib.parse.quote(nome)}&tab=9"
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        if resp.status_code != 200:
            return None
        if "does not exsists" in resp.text:
            return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        exp_values = []
        
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    date_cell = cells[0].get_text().strip()
                    if re.match(r'\d{4}-\d{2}-\d{2}', date_cell):
                        exp_values.append(parse_exp_value(cells[1].get_text()))
        
        if not exp_values:
            return None
        
        return {
            'exp_yesterday': exp_values[-1] if exp_values else 0,
            'exp_7days': sum(exp_values[-7:]),
            'exp_30days': sum(exp_values[-30:])
        }
    except:
        return None

def carregar_extras():
    for caminho in ['dados/extras.json', os.path.join(os.getcwd(), 'dados', 'extras.json')]:
        if os.path.exists(caminho):
            try:
                with open(caminho, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return [e.get('nome', '') for e in data.get('extras', []) if e.get('nome')]
            except:
                pass
    return []

def carregar_ranking_anterior():
    for caminho in ['dados/ranking.json', os.path.join(os.getcwd(), 'dados', 'ranking.json')]:
        if os.path.exists(caminho):
            try:
                with open(caminho, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
    return None

def salvar_status_aguardando(tentativa, max_tent, ranking_anterior):
    """Salva status intermediário enquanto aguarda GuildStats."""
    output_dir = os.path.join(os.getcwd(), 'dados')
    os.makedirs(output_dir, exist_ok=True)
    
    # Pega a data do ranking anterior pra mostrar
    data_anterior = None
    if ranking_anterior:
        data_anterior = ranking_anterior.get('data_xp', ranking_anterior.get('last_update_display', 'anterior'))
    
    status = {
        'ultima_execucao': datetime.now().strftime('%d/%m/%Y às %H:%M:%S'),
        'sucesso': False,
        'aguardando_atualizacao': True,
        'tentativa_atual': tentativa,
        'max_tentativas': max_tent,
        'proxima_tentativa_em': '5 minutos',
        'fonte_membros': 'TibiaData API',
        'fonte_xp': 'GuildStats.eu',
        'data_xp_exibida': data_anterior,
        'validacao': {
            'msg': f'⏳ Em atualização — dados podem estar desatualizados'
        }
    }
    
    with open(os.path.join(output_dir, 'status.json'), 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

def processar_e_salvar(membros_guild, dados_xp, aguardando=False, ranking_anterior=None):
    """Processa os dados e salva ranking e status."""
    output_dir = os.path.join(os.getcwd(), 'dados')
    os.makedirs(output_dir, exist_ok=True)
    
    # Combina dados
    jogadores = []
    nomes_processados = set()
    
    for nome_lower, xp in dados_xp.items():
        jogador = {
            'name': xp['name'],
            'level': xp['level'],
            'vocation': membros_guild.get(nome_lower, {}).get('vocation', ''),
            'exp_yesterday': xp['exp_yesterday'],
            'exp_7days': xp['exp_7days'],
            'exp_30days': xp['exp_30days'],
            'is_extra': nome_lower not in membros_guild
        }
        
        if nome_lower in membros_guild and membros_guild[nome_lower]['level'] > jogador['level']:
            jogador['level'] = membros_guild[nome_lower]['level']
        
        jogadores.append(jogador)
        nomes_processados.add(nome_lower)
    
    for nome_lower, membro in membros_guild.items():
        if nome_lower not in nomes_processados:
            jogadores.append({
                'name': membro['name'],
                'level': membro['level'],
                'vocation': membro['vocation'],
                'exp_yesterday': 0, 'exp_7days': 0, 'exp_30days': 0,
                'is_extra': False
            })
            nomes_processados.add(nome_lower)
    
    # Processa extras
    extras = carregar_extras()
    extras_reais = [e for e in extras if e.lower() not in nomes_processados]
    
    if extras_reais:
        log(f"Processando {len(extras_reais)} extras...")
        for i, nome in enumerate(extras_reais):
            if i > 0:
                time.sleep(1 if i % 5 == 0 else 0.5)
            
            voc = buscar_vocacao_individual(nome)
            if not voc:
                continue
            
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
    
    # Cria rankings
    def criar_ranking(jogadores, campo):
        filtrados = [j for j in jogadores if j.get(campo, 0) > 0]
        filtrados.sort(key=lambda x: x.get(campo, 0), reverse=True)
        return [{'rank': i, 'name': j['name'], 'vocation': j['vocation'], 
                 'level': j['level'], 'points': j[campo], 'is_extra': j.get('is_extra', False)
                } for i, j in enumerate(filtrados, 1)]
    
    total_guild = len([j for j in jogadores if not j['is_extra']])
    total_extras = len([j for j in jogadores if j.get('is_extra')])
    
    # Data da XP (ontem)
    from datetime import timedelta
    data_xp = (datetime.now() - timedelta(days=1)).strftime('%d/%m')
    
    dados_finais = {
        'guild': GUILD_NAME,
        'world': WORLD,
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'last_update_display': datetime.now().strftime('%d/%m/%Y às %H:%M'),
        'data_xp': data_xp,  # Data referente à XP (ontem)
        'total_members': total_guild,
        'total_extras': total_extras,
        'aguardando_atualizacao': aguardando,
        'rankings': {
            'yesterday': criar_ranking(jogadores, 'exp_yesterday'),
            '7days': criar_ranking(jogadores, 'exp_7days'),
            '30days': criar_ranking(jogadores, 'exp_30days')
        }
    }
    
    # Se aguardando, mantém ranking de ontem anterior
    if aguardando and ranking_anterior:
        dados_finais['rankings']['yesterday'] = ranking_anterior.get('rankings', {}).get('yesterday', [])
        dados_finais['data_xp'] = ranking_anterior.get('data_xp', 'anterior')
    
    # Salva ranking
    with open(os.path.join(output_dir, 'ranking.json'), 'w', encoding='utf-8') as f:
        json.dump(dados_finais, f, ensure_ascii=False, indent=2)
    
    # Gera status
    top5 = dados_finais['rankings']['yesterday'][:5]
    amostra = [{'pos': p['rank'], 'nome': p['name'], 'xp': f"{p['points']:,}".replace(',', '.')} for p in top5]
    
    if aguardando:
        msg = '⏳ Em atualização — dados podem estar desatualizados'
    else:
        msg = f"✅ XP do dia {data_xp} — atualizado às {datetime.now().strftime('%H:%M')}"
    
    status = {
        'ultima_execucao': datetime.now().strftime('%d/%m/%Y às %H:%M:%S'),
        'sucesso': not aguardando,
        'aguardando_atualizacao': aguardando,
        'data_xp': dados_finais['data_xp'],
        'fonte_membros': 'TibiaData API',
        'fonte_xp': 'GuildStats.eu',
        'total_membros_guild': total_guild,
        'total_extras': total_extras,
        'jogadores_com_xp_ontem': len(dados_finais['rankings']['yesterday']),
        'jogadores_com_xp_7dias': len(dados_finais['rankings']['7days']),
        'jogadores_com_xp_30dias': len(dados_finais['rankings']['30days']),
        'top5_ontem': amostra,
        'validacao': {'tem_dados': len(top5) > 0, 'msg': msg}
    }
    
    with open(os.path.join(output_dir, 'status.json'), 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    
    return dados_finais, status

def main():
    print("=" * 70)
    log(f"INICIANDO ATUALIZAÇÃO DO RANKING - {GUILD_NAME}")
    log(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Config: Max {MAX_TENTATIVAS} tentativas, intervalo {INTERVALO_RETRY//60} min")
    print("=" * 70)
    
    ranking_anterior = carregar_ranking_anterior()
    membros_guild = buscar_membros_tibiadata()
    
    if not membros_guild:
        log("ERRO: Não foi possível buscar membros!", "ERROR")
        sys.exit(1)
    
    # Loop de retry
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        log(f"Tentativa {tentativa}/{MAX_TENTATIVAS}", "RETRY")
        
        dados_xp, membros_com_xp = buscar_xp_guildstats()
        
        if membros_com_xp >= MIN_MEMBROS_COM_XP:
            log(f"GuildStats atualizado! {membros_com_xp} membros com XP ontem", "OK")
            
            dados, status = processar_e_salvar(membros_guild, dados_xp, aguardando=False)
            
            print("\n" + "=" * 70)
            log("ATUALIZAÇÃO CONCLUÍDA!")
            log(f"  Membros: {dados['total_members']} | Extras: {dados['total_extras']}")
            log(f"  Rankings: Ontem={len(dados['rankings']['yesterday'])}, 7d={len(dados['rankings']['7days'])}, 30d={len(dados['rankings']['30days'])}")
            log(f"  {status['validacao']['msg']}")
            print("=" * 70)
            return  # Sucesso!
        
        # GuildStats não atualizou ainda
        log(f"GuildStats ainda não atualizou ({membros_com_xp} membros com XP)", "WARN")
        
        if tentativa < MAX_TENTATIVAS:
            # Salva status intermediário
            salvar_status_aguardando(tentativa, MAX_TENTATIVAS, ranking_anterior)
            
            log(f"Aguardando {INTERVALO_RETRY//60} minutos para próxima tentativa...", "RETRY")
            time.sleep(INTERVALO_RETRY)
        else:
            # Última tentativa - salva com dados parciais
            log("Máximo de tentativas atingido. Salvando dados parciais.", "WARN")
            dados, status = processar_e_salvar(membros_guild, dados_xp, aguardando=True, ranking_anterior=ranking_anterior)
            
            print("\n" + "=" * 70)
            log("ATUALIZAÇÃO PARCIAL (GuildStats não atualizou)")
            log(f"  {status['validacao']['msg']}")
            print("=" * 70)

if __name__ == "__main__":
    main()

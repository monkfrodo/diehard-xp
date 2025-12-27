#!/usr/bin/env python3
"""
Scraper de XP da guild Diehard - Tibia
Gera ranking.json e status.json para o site
"""
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import time

# ============================================================
# CONFIGURAÇÕES
# ============================================================
GUILD_NAME = "Diehard"
WORLD = "Luminera"
TIMEZONE = ZoneInfo('America/Sao_Paulo')
GUILDSTATS_URL = f"https://guildstats.eu/guild?guild={GUILD_NAME}&op=3"

# Caminhos de saída
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DADOS_DIR = os.path.join(SCRIPT_DIR, '..', 'dados')
RANKING_PATH = os.path.join(DADOS_DIR, 'ranking.json')
STATUS_PATH = os.path.join(DADOS_DIR, 'status.json')
EXTRAS_PATH = os.path.join(DADOS_DIR, 'extras.json')

# ============================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================
def agora():
    """Retorna datetime atual no fuso horário de Brasília."""
    return datetime.now(TIMEZONE)

def log(msg, icon="ℹ️"):
    """Log com timestamp."""
    hora = agora().strftime('%H:%M:%S')
    print(f"[{hora}] {icon} {msg}")

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

def format_xp(valor):
    """Formata XP com pontos de milhar (padrão BR)."""
    return f"{valor:,}".replace(',', '.')

# ============================================================
# FUNÇÕES DE BUSCA DE DADOS
# ============================================================
def buscar_membros_guild():
    """Busca lista de membros da guild via TibiaData API."""
    log("Buscando membros da guild via TibiaData API...")
    try:
        url = f"https://api.tibiadata.com/v4/guild/{GUILD_NAME}"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if 'guild' in data and 'members' in data['guild']:
                membros = {}
                for member in data['guild']['members']:
                    nome_lower = member.get('name', '').lower()
                    membros[nome_lower] = {
                        'name': member.get('name', ''),
                        'vocation': member.get('vocation', ''),
                        'level': member.get('level', 0)
                    }
                log(f"Encontrados {len(membros)} membros na guild", "✅")
                return membros
    except Exception as e:
        log(f"Erro ao buscar membros: {e}", "❌")
    return {}

def buscar_xp_guildstats():
    """Busca XP de todos os jogadores no GuildStats."""
    log("Buscando XP do GuildStats...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        resp = requests.get(GUILDSTATS_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        jogadores = {}
        
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) < 15:
                continue
            
            # Encontra link do personagem
            char_link = None
            for col in cols:
                link = col.find('a')
                if link and 'character?nick=' in str(link.get('href', '')):
                    char_link = link
                    break
            
            if not char_link:
                continue
            
            nome = char_link.text.strip()
            nome_lower = nome.lower()
            
            jogadores[nome_lower] = {
                'name': nome,
                'exp_yesterday': parse_exp_value(cols[-4].text.strip()),
                'exp_7days': parse_exp_value(cols[-3].text.strip()),
                'exp_30days': parse_exp_value(cols[-2].text.strip())
            }
        
        # Conta quantos têm XP ontem (para validação)
        com_xp_ontem = sum(1 for j in jogadores.values() if j['exp_yesterday'] > 0)
        log(f"XP extraída: {len(jogadores)} jogadores, {com_xp_ontem} com XP ontem", "✅")
        
        return jogadores, com_xp_ontem
        
    except Exception as e:
        log(f"Erro ao buscar GuildStats: {e}", "❌")
        return {}, 0

def buscar_vocacao_individual(nome):
    """Busca vocação de um jogador específico (para extras)."""
    try:
        import urllib.parse
        url = f"https://api.tibiadata.com/v4/character/{urllib.parse.quote(nome)}"
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
    except:
        pass
    return None

def buscar_exp_individual(nome):
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
                    date_cell = cells[0].text.strip()
                    if len(date_cell) == 10 and date_cell[4] == '-':
                        exp_values.append(parse_exp_value(cells[1].text.strip()))
        
        if not exp_values:
            return None
        
        return {
            'exp_yesterday': exp_values[-1] if len(exp_values) >= 1 else 0,
            'exp_7days': sum(exp_values[-7:]),
            'exp_30days': sum(exp_values[-30:])
        }
    except:
        return None

def carregar_extras():
    """Carrega lista de extras do arquivo JSON."""
    if os.path.exists(EXTRAS_PATH):
        try:
            with open(EXTRAS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [e.get('nome', '') for e in data.get('extras', []) if e.get('nome')]
        except:
            pass
    return []

# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================
def main():
    # Configuração de retry
    MAX_TENTATIVAS = 36
    INTERVALO_MINUTOS = 5
    
    print("=" * 70)
    log(f"INICIANDO ATUALIZAÇÃO DO RANKING - {GUILD_NAME}")
    log(f"Data/Hora: {agora().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Config: Max {MAX_TENTATIVAS} tentativas, intervalo {INTERVALO_MINUTOS} min")
    print("=" * 70)
    
    # Garante que o diretório de dados existe
    os.makedirs(DADOS_DIR, exist_ok=True)
    
    # 1. Busca membros da guild (vocações e levels) - FONTE PRIMÁRIA
    membros_guild = buscar_membros_guild()
    
    # 2. Loop de tentativas até GuildStats atualizar
    xp_data = {}
    com_xp_ontem = 0
    
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        log(f"Tentativa {tentativa}/{MAX_TENTATIVAS}", "🔄")
        
        xp_data, com_xp_ontem = buscar_xp_guildstats()
        
        if com_xp_ontem > 0:
            log(f"GuildStats atualizado! {com_xp_ontem} membros com XP ontem", "✅")
            break
        else:
            log(f"GuildStats ainda não atualizou (0 membros com XP)", "⚠️")
            if tentativa < MAX_TENTATIVAS:
                log(f"Aguardando {INTERVALO_MINUTOS} minutos para próxima tentativa...", "🔄")
                time.sleep(INTERVALO_MINUTOS * 60)
    
    # 3. Monta lista de jogadores - COMEÇA PELOS MEMBROS DA GUILD (não pelo GuildStats)
    jogadores = []
    processados = set()
    
    # Primeiro: todos os membros da guild atual (com vocação garantida)
    for nome_lower, membro in membros_guild.items():
        xp = xp_data.get(nome_lower, {})
        jogadores.append({
            'name': membro['name'],
            'level': membro['level'],
            'vocation': membro['vocation'],
            'exp_yesterday': xp.get('exp_yesterday', 0),
            'exp_7days': xp.get('exp_7days', 0),
            'exp_30days': xp.get('exp_30days', 0),
            'is_extra': False
        })
        processados.add(nome_lower)
    
    log(f"Membros da guild processados: {len(jogadores)}", "✅")
    
    # 4. Processa extras (jogadores fora da guild que queremos trackear)
    extras = carregar_extras()
    total_extras = 0
    
    if extras:
        log(f"Processando {len(extras)} extras...")
        for nome in extras:
            nome_lower = nome.lower()
            
            # Pula se já foi processado como membro da guild
            if nome_lower in processados:
                continue
            
            time.sleep(1)  # Rate limiting
            
            # Busca vocação via TibiaData
            dados = buscar_vocacao_individual(nome)
            if not dados:
                log(f"  {nome}: não encontrado no TibiaData", "⚠️")
                continue
            
            # Busca XP - primeiro tenta do cache do GuildStats, senão busca individual
            xp = xp_data.get(nome_lower)
            if not xp:
                time.sleep(1)
                xp = buscar_exp_individual(nome)
            
            jogadores.append({
                'name': nome,
                'level': dados['level'],
                'vocation': dados['vocation'],
                'exp_yesterday': xp.get('exp_yesterday', 0) if xp else 0,
                'exp_7days': xp.get('exp_7days', 0) if xp else 0,
                'exp_30days': xp.get('exp_30days', 0) if xp else 0,
                'is_extra': True
            })
            total_extras += 1
            log(f"  {nome}: Level {dados['level']} {dados['vocation']}", "✅")
    
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
    
    ranking_ontem = criar_ranking(jogadores, 'exp_yesterday')
    ranking_7d = criar_ranking(jogadores, 'exp_7days')
    ranking_30d = criar_ranking(jogadores, 'exp_30days')
    
    # 6. Monta dados finais
    agora_br = agora()
    ontem = agora_br - timedelta(days=1)
    data_xp = ontem.strftime('%d/%m')
    
    ranking_data = {
        'guild': GUILD_NAME,
        'world': WORLD,
        'last_update': agora_br.strftime('%Y-%m-%d %H:%M:%S'),
        'last_update_display': agora_br.strftime('%d/%m/%Y às %H:%M'),
        'total_members': len(membros_guild),
        'rankings': {
            'yesterday': ranking_ontem,
            '7days': ranking_7d,
            '30days': ranking_30d
        }
    }
    
    # 7. Salva ranking.json
    with open(RANKING_PATH, 'w', encoding='utf-8') as f:
        json.dump(ranking_data, f, ensure_ascii=False, indent=2)
    
    # 8. Gera status.json para o banner
    status_data = {
        'ultima_execucao': agora_br.strftime('%d/%m/%Y às %H:%M:%S'),
        'sucesso': com_xp_ontem > 0,
        'aguardando_atualizacao': com_xp_ontem == 0,
        'data_xp': data_xp,
        'fonte_membros': 'TibiaData API',
        'fonte_xp': 'GuildStats.eu',
        'total_membros_guild': len(membros_guild),
        'total_extras': total_extras,
        'jogadores_com_xp_ontem': len(ranking_ontem),
        'jogadores_com_xp_7dias': len(ranking_7d),
        'jogadores_com_xp_30dias': len(ranking_30d),
        'top5_ontem': [
            {'pos': p['rank'], 'nome': p['name'], 'xp': format_xp(p['points'])}
            for p in ranking_ontem[:5]
        ],
        'validacao': {
            'tem_dados': com_xp_ontem > 0,
            'msg': f"✅ XP do dia {data_xp} — atualizado às {agora_br.strftime('%H:%M')}" if com_xp_ontem > 0 else f"⏳ Aguardando atualização do GuildStats"
        }
    }
    
    with open(STATUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(status_data, f, ensure_ascii=False, indent=2)
    
    # 9. Log final
    print("=" * 70)
    log("ATUALIZAÇÃO CONCLUÍDA!")
    log(f"  Membros: {len(membros_guild)} | Extras: {total_extras}")
    log(f"  Rankings: Ontem={len(ranking_ontem)}, 7d={len(ranking_7d)}, 30d={len(ranking_30d)}")
    log(f"  {status_data['validacao']['msg']}")
    print("=" * 70)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Scraper de Mortes da guild Diehard - Tibia
Gera mortes_ranking.json e mortes_status.json para o site
Acumula histórico em mortes_historico.json
"""
import requests
import json
import urllib.parse
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
TIBIADATA_API = "https://api.tibiadata.com/v4"

# Caminhos de saída
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DADOS_DIR = os.path.join(SCRIPT_DIR, '..', 'dados')
HISTORICO_PATH = os.path.join(DADOS_DIR, 'mortes_historico.json')
RANKING_PATH = os.path.join(DADOS_DIR, 'mortes_ranking.json')
STATUS_PATH = os.path.join(DADOS_DIR, 'mortes_status.json')
EXTRAS_PATH = os.path.join(DADOS_DIR, 'extras.json')
CACHE_PATH = os.path.join(DADOS_DIR, '_cache_tibiadata.json')

# Retenção: manter mortes dos últimos 90 dias
RETENCAO_DIAS = 90

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

# ============================================================
# FUNÇÕES DE BUSCA DE DADOS
# ============================================================
def buscar_membros_guild():
    """Busca lista de membros da guild via TibiaData API."""
    log("Buscando membros da guild via TibiaData API...")
    try:
        url = f"{TIBIADATA_API}/guild/{GUILD_NAME}"
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

def carregar_historico():
    """Carrega histórico de mortes do arquivo JSON."""
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('deaths', [])
        except:
            pass
    return []

def salvar_historico(deaths, cutoff_date):
    """Salva histórico de mortes, removendo mortes mais antigas que cutoff_date."""
    cutoff_str = cutoff_date.isoformat()
    pruned = [d for d in deaths if d.get('time', '') >= cutoff_str]

    data = {
        'last_update': agora().strftime('%Y-%m-%d %H:%M:%S'),
        'deaths': pruned
    }
    with open(HISTORICO_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    removed = len(deaths) - len(pruned)
    if removed > 0:
        log(f"Pruning: removidas {removed} mortes antigas (>{RETENCAO_DIAS} dias)", "🗑️")
    return pruned

def buscar_mortes_personagem(nome, tentativas=3):
    """Busca mortes de um personagem via TibiaData API."""
    url = f"{TIBIADATA_API}/character/{urllib.parse.quote(nome)}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for tentativa in range(tentativas):
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200 and resp.text.strip():
                data = resp.json()
                character = data.get('character', {})
                char_info = character.get('character', {})
                deaths_raw = character.get('deaths', [])

                deaths = []
                for death in deaths_raw:
                    reason = death.get('reason', 'Unknown')
                    involved = death.get('involved', [])
                    is_pk = any(i.get('player', False) for i in involved)

                    deaths.append({
                        'time': death.get('time', ''),
                        'level': death.get('level', 0),
                        'reason': reason,
                        'is_pk': is_pk
                    })

                return {
                    'deaths': deaths,
                    'vocation': char_info.get('vocation', ''),
                    'level': char_info.get('level', 0)
                }
            if tentativa < tentativas - 1:
                time.sleep(5)
        except:
            if tentativa < tentativas - 1:
                time.sleep(5)
    return None

def fazer_chave_morte(character, death):
    """Cria chave única para deduplicação de mortes."""
    return f"{character}|{death.get('time', '')}|{death.get('level', 0)}"

def carregar_cache_tibiadata():
    """Carrega cache de respostas TibiaData gerado pelo buscar_dados.py."""
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def limpar_cache_tibiadata():
    """Remove o cache após uso para não acumular dados velhos."""
    if os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)

# ============================================================
# CÁLCULO DE RANKINGS
# ============================================================
def calcular_rankings(historico, jogadores_info):
    """Calcula rankings de mortes por período."""
    agora_br = agora()
    hoje_inicio = agora_br.replace(hour=0, minute=0, second=0, microsecond=0)
    ontem_inicio = hoje_inicio - timedelta(days=1)
    inicio_7d = hoje_inicio - timedelta(days=7)
    inicio_30d = hoje_inicio - timedelta(days=30)

    ontem_str = ontem_inicio.isoformat()
    hoje_str = hoje_inicio.isoformat()
    inicio_7d_str = inicio_7d.isoformat()
    inicio_30d_str = inicio_30d.isoformat()

    # Agrupa mortes por jogador
    mortes_por_jogador = {}
    for death in historico:
        char = death.get('character', '')
        if char not in mortes_por_jogador:
            mortes_por_jogador[char] = []
        mortes_por_jogador[char].append(death)

    # Calcula contagens por período para cada jogador
    rankings = {'yesterday': [], '7days': [], '30days': [], 'alltime': []}

    for nome, info in jogadores_info.items():
        mortes = mortes_por_jogador.get(nome, [])
        if not mortes:
            continue

        count_yesterday = 0
        count_7d = 0
        count_30d = 0
        count_all = len(mortes)

        deaths_yesterday = []
        deaths_7d = []
        deaths_30d = []

        for m in mortes:
            t = m.get('time', '')
            if t >= ontem_str and t < hoje_str:
                count_yesterday += 1
                deaths_yesterday.append(m)
            if t >= inicio_7d_str:
                count_7d += 1
                deaths_7d.append(m)
            if t >= inicio_30d_str:
                count_30d += 1
                deaths_30d.append(m)

        base = {
            'name': info['name'],
            'vocation': info['vocation'],
            'level': info['level'],
            'is_extra': info.get('is_extra', False)
        }

        if count_yesterday > 0:
            entry = {**base, 'death_count': count_yesterday, 'deaths': sorted(deaths_yesterday, key=lambda x: x.get('time', ''), reverse=True)}
            rankings['yesterday'].append(entry)
        if count_7d > 0:
            entry = {**base, 'death_count': count_7d, 'deaths': sorted(deaths_7d, key=lambda x: x.get('time', ''), reverse=True)}
            rankings['7days'].append(entry)
        if count_30d > 0:
            entry = {**base, 'death_count': count_30d, 'deaths': sorted(deaths_30d, key=lambda x: x.get('time', ''), reverse=True)}
            rankings['30days'].append(entry)
        if count_all > 0:
            entry = {**base, 'death_count': count_all, 'deaths': sorted(mortes, key=lambda x: x.get('time', ''), reverse=True)[:20]}
            rankings['alltime'].append(entry)

    # Ordena e adiciona rank
    for period in rankings:
        rankings[period].sort(key=lambda x: x['death_count'], reverse=True)
        for i, entry in enumerate(rankings[period], 1):
            entry['rank'] = i

    return rankings

# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================
def main():
    print("=" * 70)
    log(f"INICIANDO SCRAPER DE MORTES - {GUILD_NAME}")
    log(f"Data/Hora: {agora().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    os.makedirs(DADOS_DIR, exist_ok=True)

    # 1. Carrega histórico existente
    historico = carregar_historico()
    chaves_existentes = set()
    for d in historico:
        chave = fazer_chave_morte(d.get('character', ''), d)
        chaves_existentes.add(chave)
    log(f"Histórico carregado: {len(historico)} mortes existentes")

    # 2. Busca membros da guild
    membros_guild = buscar_membros_guild()

    # 3. Carrega extras
    extras = carregar_extras()

    # 4. Monta lista completa de jogadores
    jogadores_info = {}
    processados = set()

    for nome_lower, membro in membros_guild.items():
        jogadores_info[membro['name']] = {
            'name': membro['name'],
            'vocation': membro['vocation'],
            'level': membro['level'],
            'is_extra': False
        }
        processados.add(nome_lower)

    for nome in extras:
        if nome.lower() not in processados:
            jogadores_info[nome] = {
                'name': nome,
                'vocation': '',
                'level': 0,
                'is_extra': True
            }
            processados.add(nome.lower())

    log(f"Total de jogadores a buscar: {len(jogadores_info)}")

    # 5. Carrega cache do buscar_dados.py (extras já buscados)
    cache = carregar_cache_tibiadata()
    cache_hits = 0

    def processar_mortes(nome, deaths, vocation, level):
        """Processa mortes de um jogador (cache ou API)."""
        nonlocal mortes_novas, jogadores_com_mortes
        info = jogadores_info[nome]

        if vocation:
            info['vocation'] = vocation
        if level:
            info['level'] = level

        if not deaths:
            return

        jogadores_com_mortes += 1
        for death in deaths:
            chave = fazer_chave_morte(nome, death)
            if chave not in chaves_existentes:
                historico.append({
                    'character': nome,
                    'time': death['time'],
                    'level': death['level'],
                    'reason': death['reason'],
                    'is_pk': death['is_pk']
                })
                chaves_existentes.add(chave)
                mortes_novas += 1

    # 5a. Processa jogadores do cache (sem requests)
    for nome in list(jogadores_info.keys()):
        if nome in cache:
            cached = cache[nome]
            processar_mortes(nome, cached.get('deaths', []), cached.get('vocation', ''), cached.get('level', 0))
            cache_hits += 1

    if cache_hits > 0:
        log(f"Cache: {cache_hits} jogadores reaproveitados do scraper de XP", "♻️")

    # 5b. Busca mortes dos jogadores restantes via API
    jogadores_restantes = [n for n in jogadores_info if n not in cache]
    log(f"API: {len(jogadores_restantes)} jogadores a buscar via TibiaData")

    mortes_novas = 0
    jogadores_com_mortes = 0
    falhas = 0

    for i, nome in enumerate(jogadores_restantes, 1):
        if i > 1:
            time.sleep(1.5)

        if i % 20 == 0:
            log(f"Progresso: {i}/{len(jogadores_restantes)} jogadores processados...")

        resultado = buscar_mortes_personagem(nome)
        if resultado is None:
            falhas += 1
            continue

        processar_mortes(nome, resultado['deaths'], resultado['vocation'], resultado['level'])

    log(f"Busca concluída: {mortes_novas} mortes novas, {jogadores_com_mortes} jogadores com mortes, {falhas} falhas", "✅")

    # Limpa cache após uso
    limpar_cache_tibiadata()

    # 6. Pruning e salvar histórico
    cutoff = agora() - timedelta(days=RETENCAO_DIAS)
    cutoff_naive = cutoff.strftime('%Y-%m-%dT00:00:00Z')
    historico = [d for d in historico if d.get('time', '') >= cutoff_naive]
    salvar_historico(historico, cutoff)

    # 7. Calcula rankings
    rankings = calcular_rankings(historico, jogadores_info)

    # 8. Salva mortes_ranking.json
    agora_br = agora()
    ranking_data = {
        'guild': GUILD_NAME,
        'world': WORLD,
        'last_update': agora_br.strftime('%Y-%m-%d %H:%M:%S'),
        'last_update_display': agora_br.strftime('%d/%m/%Y às %H:%M'),
        'total_members': len(membros_guild),
        'rankings': rankings
    }

    with open(RANKING_PATH, 'w', encoding='utf-8') as f:
        json.dump(ranking_data, f, ensure_ascii=False, indent=2)

    # 9. Salva mortes_status.json
    status_data = {
        'ultima_execucao': agora_br.strftime('%d/%m/%Y às %H:%M:%S'),
        'sucesso': True,
        'total_jogadores_buscados': len(jogadores_info),
        'mortes_novas': mortes_novas,
        'total_historico': len(historico),
        'falhas': falhas,
        'jogadores_com_mortes_ontem': len(rankings['yesterday']),
        'jogadores_com_mortes_7dias': len(rankings['7days']),
        'jogadores_com_mortes_30dias': len(rankings['30days']),
        'jogadores_com_mortes_alltime': len(rankings['alltime'])
    }

    with open(STATUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(status_data, f, ensure_ascii=False, indent=2)

    # 10. Log final
    print("=" * 70)
    log("SCRAPER DE MORTES CONCLUÍDO!")
    log(f"  Jogadores: {len(jogadores_info)} | Falhas: {falhas}")
    log(f"  Mortes novas: {mortes_novas} | Total histórico: {len(historico)}")
    log(f"  Rankings: Ontem={len(rankings['yesterday'])}, 7d={len(rankings['7days'])}, 30d={len(rankings['30days'])}, All={len(rankings['alltime'])}")
    print("=" * 70)

if __name__ == "__main__":
    main()

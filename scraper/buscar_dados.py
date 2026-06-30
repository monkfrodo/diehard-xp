#!/usr/bin/env python3
"""
Scraper de XP da guild Diehard - Tibia
Gera ranking.json e status.json para o site
"""
import requests
from bs4 import BeautifulSoup
import json
import html as html_module
import re
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import time
from http_client import fetch

# ============================================================
# CONFIGURAÇÕES
# ============================================================
GUILD_NAME = "Diehard"
WORLD = "Luminera"
TIMEZONE = ZoneInfo('America/Sao_Paulo')
GUILDSTATS_URL = f"https://guildstats.eu/include/guild/tab.php?guild={GUILD_NAME}&tab=timeonline"
GUILDSTATS_REFERER = f"https://guildstats.eu/guild?guild={GUILD_NAME}&world={WORLD}&op=3"
GUILDSTATS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': GUILDSTATS_REFERER
}

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

def encode_guildstats_nick(nome):
    """Codifica o nick no formato que o JS do GuildStats usa nas abas AJAX."""
    escaped = html_module.escape(nome, quote=True).replace('&#x27;', '&apos;')
    return urllib.parse.quote(escaped, safe='')

def extrair_char_nick_param(html):
    """Extrai o charNickParam renderizado na página completa do personagem."""
    match = re.search(r"charNickParam\s*=\s*'([^']*)'", html)
    return match.group(1) if match else None

# ============================================================
# FUNÇÕES DE BUSCA DE DADOS
# ============================================================
def buscar_html_guildstats():
    """Busca a tabela AJAX diretamente e usa o bypass anti-bot como fallback."""
    try:
        resp = requests.get(GUILDSTATS_URL, headers=GUILDSTATS_HEADERS, timeout=30)
        resp.raise_for_status()
        html = resp.text
        if '<td' in html and ('character/' in html or 'character?nick=' in html):
            log("Tabela AJAX do GuildStats carregada diretamente", "✅")
            return html
        log("GuildStats retornou HTML sem dados da tabela; tentando fallback", "⚠️")
    except Exception as e:
        log(f"Falha na chamada direta ao GuildStats ({e}); tentando fallback", "⚠️")

    return fetch(GUILDSTATS_URL)

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
    try:
        html = buscar_html_guildstats()
        
        soup = BeautifulSoup(html, 'html.parser')
        jogadores = {}
        xp_columns = {}

        for table in soup.find_all('table'):
            headers = [th.get_text(' ', strip=True).lower() for th in table.find_all('th')]
            if 'exp yesterday' in headers and 'exp 7 days' in headers and 'exp 30 days' in headers:
                xp_columns = {
                    'exp_yesterday': headers.index('exp yesterday'),
                    'exp_7days': headers.index('exp 7 days'),
                    'exp_30days': headers.index('exp 30 days')
                }
                break

        if not xp_columns:
            raise ValueError("Colunas de XP não encontradas na tabela do GuildStats")
        
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) <= max(xp_columns.values()):
                continue
            
            # Encontra link do personagem
            char_link = None
            for col in cols:
                link = col.find('a')
                href = link.get('href', '') if link else ''
                if link and ('character/' in href or 'character?nick=' in href):
                    char_link = link
                    break
            
            if not char_link:
                continue
            
            nome = char_link.text.strip()
            nome_lower = nome.lower()
            
            def get_col_xp(col):
                sv = col.get('data-sort-value')
                if sv is not None:
                    try: return int(sv)
                    except: pass
                return parse_exp_value(col.text.strip().split('\n')[0].strip())

            jogadores[nome_lower] = {
                'name': nome,
                'exp_yesterday': get_col_xp(cols[xp_columns['exp_yesterday']]),
                'exp_7days': get_col_xp(cols[xp_columns['exp_7days']]),
                'exp_30days': get_col_xp(cols[xp_columns['exp_30days']])
            }
        
        # Conta quantos têm XP ontem (para validação)
        com_xp_ontem = sum(1 for j in jogadores.values() if j['exp_yesterday'] > 0)
        log(f"XP extraída: {len(jogadores)} jogadores, {com_xp_ontem} com XP ontem", "✅")
        
        return jogadores, com_xp_ontem
        
    except Exception as e:
        log(f"Erro ao buscar GuildStats: {e}", "❌")
        return {}, 0

def buscar_vocacao_individual(nome, tentativas=3):
    """Busca vocação de um jogador específico (para extras) com retry.
    Também extrai mortes e salva no cache para o scraper de mortes reaproveitar."""
    import urllib.parse
    url = f"https://api.tibiadata.com/v4/character/{urllib.parse.quote(nome)}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for tentativa in range(tentativas):
        try:
            resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code == 200 and resp.text.strip():
                data = resp.json()
                character = data.get('character', {})
                char = character.get('character', {})
                if char and char.get('name'):
                    # Extrai mortes para o cache
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
                    _salvar_cache_tibiadata(nome, deaths, char.get('vocation', ''), char.get('level', 0))

                    return {
                        'name': char.get('name', nome),
                        'vocation': char.get('vocation', ''),
                        'level': char.get('level', 0),
                        'world': char.get('world', '')
                    }
            # Se resposta vazia ou erro, espera e tenta de novo
            if tentativa < tentativas - 1:
                time.sleep(5)
        except:
            if tentativa < tentativas - 1:
                time.sleep(5)
    return None


# Cache de respostas TibiaData para o scraper de mortes reaproveitar
CACHE_PATH = os.path.join(DADOS_DIR, '_cache_tibiadata.json')

def _carregar_cache_tibiadata():
    """Carrega cache existente ou retorna dict vazio."""
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def _salvar_cache_tibiadata(nome, deaths, vocation, level):
    """Salva dados de um personagem no cache."""
    cache = _carregar_cache_tibiadata()
    cache[nome] = {
        'deaths': deaths,
        'vocation': vocation,
        'level': level,
        'fetched_at': agora().strftime('%Y-%m-%d %H:%M:%S')
    }
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def buscar_html_exp_individual(nome, timeout=15, page_html=None):
    """Busca a aba de XP individual tentando os formatos de nick do GuildStats."""
    nick_params = []
    page_param = extrair_char_nick_param(page_html or '')
    if page_param:
        nick_params.append(page_param)

    for param in (
        urllib.parse.quote(nome, safe=''),
        encode_guildstats_nick(nome)
    ):
        if param not in nick_params:
            nick_params.append(param)

    ultimo_erro = None
    for nick_param in nick_params:
        url = f"https://guildstats.eu/include/character/tab.php?nick={nick_param}&tab=experience"
        try:
            html = fetch(url, timeout=timeout)
        except Exception as e:
            ultimo_erro = e
            continue

        if "does not exsists" in html or "don't have in our datebase" in html:
            continue

        if extrair_exp_individual(html):
            return html

    if ultimo_erro:
        raise ultimo_erro
    return None

def extrair_exp_individual(html):
    """Extrai XP diário da aba individual, ordenando do registro mais recente."""
    registros = []
    soup = BeautifulSoup(html, 'html.parser')

    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            data = cells[0].text.strip()[:10]
            if len(data) != 10 or data[4] != '-' or data[7] != '-':
                continue

            sort_val = cells[1].get('data-sort-value')
            if sort_val is not None:
                try:
                    valor = int(sort_val)
                except ValueError:
                    valor = 0
            else:
                raw = cells[1].text.strip().split('\n')[0].strip()
                valor = parse_exp_value(raw)

            registros.append((data, valor))

    registros.sort(key=lambda registro: registro[0], reverse=True)
    exp_values = [valor for _, valor in registros]

    if not exp_values:
        return None

    return {
        'exp_yesterday': exp_values[0],
        'exp_7days': sum(exp_values[:7]),
        'exp_30days': sum(exp_values[:30])
    }

def buscar_dados_guildstats_individual(nome):
    """Busca dados completos de um jogador na página individual do GuildStats (vocação, level e XP)."""
    try:
        url = f"https://guildstats.eu/character/{urllib.parse.quote(nome)}"
        html = fetch(url, timeout=20)

        if "does not exsists" in html or "don't have in our datebase" in html:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        # Busca vocação e level da página principal
        vocation = ''
        level = 0

        # Procura nas divs de informações do personagem
        for div in soup.find_all('div'):
            spans = div.find_all('span')
            if len(spans) >= 2:
                label = spans[0].text.strip().lower()
                if label == 'vocation:':
                    vocation = spans[1].text.strip()
                elif label == 'level':
                    try:
                        level = int(spans[1].text.strip().replace(',', '').replace('.', ''))
                    except ValueError:
                        pass

        # Agora busca XP na aba de experiência
        html_xp = buscar_html_exp_individual(nome, timeout=20, page_html=html)

        xp = extrair_exp_individual(html_xp or '') or {
            'exp_yesterday': 0,
            'exp_7days': 0,
            'exp_30days': 0
        }

        return {
            'vocation': vocation,
            'level': level,
            **xp
        }
    except Exception as e:
        log(f"Erro ao buscar dados do GuildStats para {nome}: {e}", "⚠️")
        return None

def buscar_exp_individual(nome):
    """Busca XP de um jogador na página individual do GuildStats."""
    try:
        html = buscar_html_exp_individual(nome, timeout=15)
        if not html:
            return None

        return extrair_exp_individual(html)
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
        
        try:
            xp_data, com_xp_ontem = buscar_xp_guildstats()
            
            if com_xp_ontem >= 10:
                log(f"GuildStats atualizado! {com_xp_ontem} membros com XP ontem", "✅")
                break
            else:
                log(f"GuildStats ainda não atualizou ({com_xp_ontem} jogadores com XP ontem, aguardando 10+)", "⚠️")
        except Exception as e:
            if "403" in str(e):
                log(f"ERRO: Bloqueio anti-bot detectado (403).", "🚫")
            else:
                log(f"Erro inesperado: {e}", "❌")
            
            # Se falhou por bloqueio ou erro, tratamos como "não atualizou" para o retry loop seguir
            com_xp_ontem = 0
            
        if tentativa < MAX_TENTATIVAS:
            log(f"Aguardando {INTERVALO_MINUTOS} minutos para próxima tentativa...", "🔄")
            time.sleep(INTERVALO_MINUTOS * 60)
    
    # 3. Monta lista de jogadores - COMEÇA PELOS MEMBROS DA GUILD (não pelo GuildStats)
    jogadores = []
    processados = set()
    
    # Primeiro: todos os membros da guild atual (com vocação garantida)
    sem_xp = []  # membros sem XP em nenhum período no tab.php
    for nome_lower, membro in membros_guild.items():
        xp = xp_data.get(nome_lower, {})
        exp_y = xp.get('exp_yesterday', 0)
        exp_7 = xp.get('exp_7days', 0)
        exp_30 = xp.get('exp_30days', 0)
        jogadores.append({
            'name': membro['name'],
            'level': membro['level'],
            'vocation': membro['vocation'],
            'exp_yesterday': exp_y,
            'exp_7days': exp_7,
            'exp_30days': exp_30,
            'is_extra': False
        })
        processados.add(nome_lower)
        if exp_y == 0:  # busca individual para corrigir yesterday mesmo se 7d/30d ok
            sem_xp.append(nome_lower)

    log(f"Membros da guild: {len(jogadores)} ({len(sem_xp)} sem XP no tab.php — buscando individualmente...)", "✅")

    # Busca individual para membros sem XP no tab.php
    atualizados = 0
    for i, nome_lower in enumerate(sem_xp):
        membro = membros_guild[nome_lower]
        time.sleep(1)
        xp = buscar_exp_individual(membro['name'])
        if xp and xp.get('exp_yesterday', 0) > 0:
            for j in jogadores:
                if j['name'] == membro['name']:
                    j['exp_yesterday'] = xp['exp_yesterday']
                    # 7d/30d: usa individual só se guild tab tiver 0
                    if j['exp_7days'] == 0:
                        j['exp_7days'] = xp.get('exp_7days', 0)
                    if j['exp_30days'] == 0:
                        j['exp_30days'] = xp.get('exp_30days', 0)
                    break
            atualizados += 1
        if (i + 1) % 20 == 0:
            log(f"  Busca individual: {i+1}/{len(sem_xp)}, {atualizados} com XP", "🔄")

    log(f"Busca individual concluída: {atualizados}/{len(sem_xp)} membros com XP encontrado", "✅")
    
    # 4. Processa extras (jogadores fora da guild que queremos trackear)
    extras = carregar_extras()
    total_extras = 0

    if extras:
        log(f"Processando {len(extras)} extras...")
        for nome in extras:
            nome_lower = nome.lower()

            # Pula se já foi processado como membro da guild
            if nome_lower in processados:
                log(f"  {nome}: já está na guild, pulando", "ℹ️")
                continue

            time.sleep(2)  # Rate limiting

            # Tenta buscar vocação via TibiaData primeiro
            dados = buscar_vocacao_individual(nome)

            if dados:
                nome_atual = dados.get('name') or nome
                nome_atual_lower = nome_atual.lower()
                mundo_atual = dados.get('world', '')

                if mundo_atual and mundo_atual != WORLD:
                    log(f"  {nome}: personagem atual é {nome_atual} em {mundo_atual}, pulando (esperado: {WORLD})", "⚠️")
                    continue

                if nome_atual_lower in processados:
                    log(f"  {nome}: já processado como {nome_atual}, pulando", "ℹ️")
                    continue

                if nome_atual != nome:
                    log(f"  {nome}: nome atual detectado pela TibiaData é {nome_atual}", "ℹ️")

                # TibiaData funcionou - busca XP separadamente
                xp = xp_data.get(nome_atual_lower)
                if not xp:
                    time.sleep(2)
                    xp = buscar_exp_individual(nome_atual)

                jogadores.append({
                    'name': nome_atual,
                    'level': dados['level'],
                    'vocation': dados['vocation'],
                    'exp_yesterday': xp.get('exp_yesterday', 0) if xp else 0,
                    'exp_7days': xp.get('exp_7days', 0) if xp else 0,
                    'exp_30days': xp.get('exp_30days', 0) if xp else 0,
                    'is_extra': True
                })
                processados.add(nome_atual_lower)
                total_extras += 1
                log(f"  {nome_atual}: Level {dados['level']} {dados['vocation']} (TibiaData)", "✅")
            else:
                # TibiaData falhou - usa GuildStats como fonte completa (fallback)
                log(f"  {nome}: TibiaData timeout, tentando GuildStats...", "⚠️")
                time.sleep(2)
                dados_gs = buscar_dados_guildstats_individual(nome)

                if dados_gs:
                    jogadores.append({
                        'name': nome,
                        'level': dados_gs['level'],
                        'vocation': dados_gs['vocation'],
                        'exp_yesterday': dados_gs['exp_yesterday'],
                        'exp_7days': dados_gs['exp_7days'],
                        'exp_30days': dados_gs['exp_30days'],
                        'is_extra': True
                    })
                    processados.add(nome_lower)
                    total_extras += 1
                    log(f"  {nome}: Level {dados_gs['level']} {dados_gs['vocation']} (GuildStats)", "✅")
                else:
                    log(f"  {nome}: não encontrado em nenhuma fonte", "❌")
    
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

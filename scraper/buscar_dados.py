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
        
        exp_yesterday = exp_por_data.get(datas_ordenadas[0], 0) if len(datas_ordenadas) > 0 else 0
        exp_7days = sum(exp_por_data.get(d, 0) for d in datas_ordenadas[:7])
        exp_30days = sum(exp_por_data.get(d, 0) for d in datas_ordenadas[:30])
        
        print(f"    XP: ontem={exp_yesterday:,}, 7d={exp_7days:,}, 30d={exp_30days:,}")
        return {'exp_yesterday': exp_yesterday, 'exp_7days': exp_7days, 'exp_30days': exp_30days}
        
    except Exception as e:
        print(f"    Erro buscando XP de {nome}: {e}")
    return None

def buscar_mortes_jogador(nome):
    """Busca mortes recentes de um jogador no GuildStats (tab=5)."""
    try:
        url = f"https://guildstats.eu/character?nick={requests.utils.quote(nome)}&tab=5"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return []
        
        if "does not exsists" in resp.text or "don't have in our datebase" in resp.text:
            return []
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        mortes = []
        
        page_text = soup.get_text()
        
        # Procura padrões de morte: "DD-MM-YYYY HH:MM Killed at level XXX by ..."
        death_pattern = re.findall(
            r'(\d{2}-\d{2}-\d{4})\s+\d{2}:\d{2}\s+Killed at level\s+(\d+)\s+by\s+([^.]+)',
            page_text,
            re.IGNORECASE
        )
        
        for match in death_pattern:
            data = match[0]
            level = int(match[1]) if match[1] else 0
            reason = match[2].strip()[:60] if match[2] else ''
            
            mortes.append({
                'date': data,
                'level': level,
                'reason': reason
            })
            
            if len(mortes) >= 5:
                break
        
        return mortes
        
    except Exception as e:
        return []

def buscar_dados_guild():
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
        
        jogadores.append({
            'name': nome,
            'level': level,
            'exp_yesterday': exp_values[0] if len(exp_values) > 0 else 0,
            'exp_7days': exp_values[1] if len(exp_values) > 1 else 0,
            'exp_30days': exp_values[2] if len(exp_values) > 2 else 0,
            'vocation': '',
            'is_extra': False
        })
    
    print(f"  ✓ {len(jogadores)} jogadores encontrados")
    return jogadores

def buscar_todas_mortes(jogadores, vocacoes_guild):
    """Busca mortes de todos os jogadores."""
    print(f"\nBuscando mortes de {len(jogadores)} jogadores...")
    todas_mortes = []
    
    for i, jogador in enumerate(jogadores):
        nome = jogador['name']
        mortes = buscar_mortes_jogador(nome)
        
        if mortes:
            vocation = jogador.get('vocation', '')
            if not vocation and nome.lower() in vocacoes_guild:
                vocation = vocacoes_guild[nome.lower()].get('vocation', '')
            
            for morte in mortes:
                todas_mortes.append({
                    'name': nome,
                    'level': morte['level'] if morte['level'] > 0 else jogador.get('level', 0),
                    'vocation': vocation,
                    'date': morte['date'],
                    'reason': morte['reason']
                })
        
        if (i + 1) % 25 == 0:
            print(f"  Progresso: {i + 1}/{len(jogadores)} jogadores, {len(todas_mortes)} mortes...")
        
        time.sleep(0.3)
    
    # Ordena por data (mais recente primeiro) - converte DD-MM-YYYY para YYYYMMDD
    def parse_date(d):
        try:
            parts = d.split('-')
            if len(parts) == 3:
                return f"{parts[2]}{parts[1]}{parts[0]}"
        except:
            pass
        return d
    
    todas_mortes.sort(key=lambda x: parse_date(x.get('date', '')), reverse=True)
    
    print(f"  ✓ {len(todas_mortes)} mortes encontradas no total")
    return todas_mortes[:100]

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
    
    vocacoes_guild = buscar_vocacoes_guild_tibiadata()
    jogadores = buscar_dados_guild()
    
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
            'exp_yesterday': exp['exp_yesterday'] if exp else 0,
            'exp_7days': exp['exp_7days'] if exp else 0,
            'exp_30days': exp['exp_30days'] if exp else 0,
            'is_extra': True
        })
    
    mortes = buscar_todas_mortes(jogadores, vocacoes_guild)
    
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
            'yesterday': criar_ranking(jogadores, 'exp_yesterday', TOP_N),
            '7days': criar_ranking(jogadores, 'exp_7days', TOP_N),
            '30days': criar_ranking(jogadores, 'exp_30days', TOP_N)
        },
        'deaths': mortes
    }
    
    output_path = os.path.join(os.getcwd(), 'dados', 'ranking.json')
    print(f"\nSalvando em: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dados_finais, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ Concluído!")
    print(f"   Ontem: {len(dados_finais['rankings']['yesterday'])} jogadores")
    print(f"   7 dias: {len(dados_finais['rankings']['7days'])} jogadores")  
    print(f"   30 dias: {len(dados_finais['rankings']['30days'])} jogadores")
    print(f"   Mortes: {len(dados_finais['deaths'])} registros")

if __name__ == "__main__":
    main()

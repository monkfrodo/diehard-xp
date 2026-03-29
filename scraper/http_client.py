
import time
import requests

def fetch(url, timeout=30) -> str:
    """
    Retorna HTML da URL, tentando múltiplas estratégias anti-bot:
    1. cloudscraper
    2. curl_cffi
    3. Playwright
    """
    
    # 1. curl_cffi (Impersonate browser TLS fingerprint)
    try:
        from curl_cffi import requests as curl_requests
        # print(f"  [http_client] Tentando curl_cffi (chrome) para {url}...")
        resp = curl_requests.get(url, impersonate="chrome", timeout=timeout)
        if resp.status_code == 200 and "Just a moment..." not in resp.text:
            print(f"  [http_client] ✅ Sucesso com curl_cffi ({url[:50]}...)")
            return resp.text
        if resp.status_code == 403 or "Just a moment..." in resp.text:
            print(f"  [http_client] ⚠️ curl_cffi falhou (403 ou block)")
    except ImportError:
        pass
    except Exception as e:
        print(f"  [http_client] ❌ Erro no curl_cffi: {e}")

    # 2. cloudscraper (Tenta resolver Cloudflare v1/v2)
    try:
        import cloudscraper
        # print(f"  [http_client] Tentando cloudscraper para {url}...")
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=timeout)
        if resp.status_code == 200 and "Just a moment..." not in resp.text:
            print(f"  [http_client] ✅ Sucesso com cloudscraper ({url[:50]}...)")
            return resp.text
        if resp.status_code == 403 or "Just a moment..." in resp.text:
            print(f"  [http_client] ⚠️ cloudscraper falhou (403 ou block)")
    except ImportError:
        pass
    except Exception as e:
        print(f"  [http_client] ❌ Erro no cloudscraper: {e}")

    # 3. Playwright (Último recurso, renderiza JS completo)
    try:
        from playwright.sync_api import sync_playwright
        print(f"  [http_client] ⚠️ Iniciando Playwright para {url}...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # User Agent moderno para evitar bloqueios triviais
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            page = browser.new_page(user_agent=ua)
            
            # Navega até a URL
            response = page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            
            # Pequena espera extra para segurança
            time.sleep(3)
            
            if response and response.status == 200:
                content = page.content()
                browser.close()
                print(f"  [http_client] ✅ Sucesso com Playwright ({url[:50]}...)")
                return content
            
            status = response.status if response else "unknown"
            browser.close()
            print(f"  [http_client] ❌ Playwright falhou com status {status}")
                
    except ImportError:
        print("  [http_client] ❌ Playwright não instalado")
    except Exception as e:
        print(f"  [http_client] ❌ Erro crítico no Playwright: {e}")

    # Se todas as estratégias falharem
    raise Exception(f"Bloqueio 403 detectado em {url}. Nenhuma estratégia de bypass funcionou.")

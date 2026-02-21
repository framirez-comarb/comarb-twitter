#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  COMARB Twitter/X Sentiment Analysis Dashboard
  Analiza tweets sobre sistemas tributarios argentinos
  Palabras clave: comarb, sifere, sircar, sirpei, sircreb, sircupa, sirtac
═══════════════════════════════════════════════════════════════

  Modos de ejecución:
  - LOCAL:  python main.py  (interactivo)
  - CI:     GitHub Actions con secrets

  Secrets soportados:
  - TWITTER_COOKIES        → cookies base64 (método principal)
  - TWITTER_ACCOUNTS       → JSON con múltiples cuentas (fallback + rotación)
  - TWITTER_USERNAME       → usuario simple (fallback básico)
  - TWITTER_EMAIL          → email simple (fallback básico)
  - TWITTER_PASSWORD       → contraseña simple (fallback básico)
═══════════════════════════════════════════════════════════════
"""

import asyncio
import base64
import json
import os
import sys
import random
from datetime import datetime

# ── Detectar modo CI ──
CI_MODE = os.environ.get("CI", "").lower() == "true"
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "docs")

# ── Verificar e instalar dependencias ──
def install_dependencies():
    """Instala las dependencias necesarias."""
    if not CI_MODE:
        print("📦 Verificando twikit (última versión)...")
    os.system(f"{sys.executable} -m pip install twikit --upgrade -q 2>/dev/null")

    deps = {"textblob": "textblob"}
    for module, package in deps.items():
        try:
            __import__(module)
        except ImportError:
            if not CI_MODE:
                print(f"📦 Instalando {package}...")
            os.system(f"{sys.executable} -m pip install {package} -q 2>/dev/null")

    try:
        from textblob import TextBlob
        TextBlob("test").sentiment
    except Exception:
        if not CI_MODE:
            print("📦 Descargando datos de TextBlob...")
        os.system(f"{sys.executable} -m textblob.download_corpora lite -q 2>/dev/null")

install_dependencies()

from twikit import Client
from textblob import TextBlob
from report_generator import generate_html_report

# ── Configuración ──
KEYWORDS = ["comarb", "sifere", "sircar", "sirpei", "sircreb", "sircupa", "sirtac"]
MAX_TWEETS_PER_KEYWORD = 200
COOKIES_FILE = "twitter_cookies.json"
DATA_FILE = "tweets_data.json"
REPORT_FILE = os.path.join(OUTPUT_DIR, "index.html")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
PAUSE_BETWEEN_KEYWORDS = 30  # segundos entre cada keyword


# ═══════════════════════════════════════════════════════════════
#  GESTIÓN DE CUENTAS MÚLTIPLES
# ═══════════════════════════════════════════════════════════════

class AccountManager:
    """Gestiona múltiples cuentas de Twitter para rotación."""

    def __init__(self):
        self.accounts = []
        self.current_index = 0
        self.clients = {}  # account_id -> Client
        self._load_accounts()

    def _load_accounts(self):
        """Carga cuentas desde secrets o input del usuario."""
        if CI_MODE:
            self._load_accounts_ci()
        # En modo local las cuentas se gestionan interactivamente

    def _load_accounts_ci(self):
        """Carga cuentas desde GitHub Secrets."""

        # ── Método 1: TWITTER_ACCOUNTS (JSON con múltiples cuentas) ──
        accounts_json = os.environ.get("TWITTER_ACCOUNTS")
        if accounts_json:
            try:
                # Puede estar en base64 o en JSON directo
                try:
                    decoded = base64.b64decode(accounts_json).decode("utf-8")
                    self.accounts = json.loads(decoded)
                except Exception:
                    self.accounts = json.loads(accounts_json)

                print(f"✅ CI: {len(self.accounts)} cuentas cargadas desde TWITTER_ACCOUNTS")
                # Mezclar para distribuir el uso
                random.shuffle(self.accounts)
                return
            except Exception as e:
                print(f"⚠️  CI: error parseando TWITTER_ACCOUNTS: {e}")

        # ── Método 2: credenciales simples ──
        username = os.environ.get("TWITTER_USERNAME")
        email = os.environ.get("TWITTER_EMAIL")
        password = os.environ.get("TWITTER_PASSWORD")

        if username and password:
            self.accounts = [{
                "username": username,
                "email": email or "",
                "password": password,
                "label": username
            }]
            print(f"✅ CI: cuenta cargada desde TWITTER_USERNAME/PASSWORD")

    def has_accounts(self):
        return len(self.accounts) > 0

    def get_next_account(self):
        """Retorna la siguiente cuenta en la rotación."""
        if not self.accounts:
            return None
        account = self.accounts[self.current_index % len(self.accounts)]
        self.current_index += 1
        return account

    def get_account_count(self):
        return len(self.accounts)


# ═══════════════════════════════════════════════════════════════
#  AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════

def get_credentials():
    """Obtiene las credenciales de Twitter del usuario (modo local)."""
    print("\n" + "═" * 60)
    print("  🔐 LOGIN DE TWITTER/X")
    print("═" * 60)
    print("  Necesitás una cuenta de Twitter/X para buscar tweets.")
    print("  Las credenciales solo se usan para loguearte y se")
    print("  guardan como cookies locales para no pedirlas de nuevo.\n")

    username = input("  👤 Usuario de Twitter (sin @): ").strip()
    email = input("  📧 Email de la cuenta: ").strip()
    password = input("  🔑 Contraseña: ").strip()

    return username, email, password


def get_browser_cookies():
    """Obtiene cookies de Twitter/X desde el navegador del usuario."""
    print("\n" + "═" * 60)
    print("  🍪 IMPORTAR COOKIES DEL NAVEGADOR")
    print("═" * 60)
    print("  1. Abrí Twitter/X en tu navegador y logueate normalmente")
    print("  2. Presioná F12 → Application → Cookies → https://x.com")
    print("  3. Copiá los valores de 'auth_token' y 'ct0'")
    print()

    auth_token = input("  🔑 auth_token: ").strip()
    ct0 = input("  🔑 ct0: ").strip()

    if not auth_token or not ct0:
        print("  ❌ Ambos valores son obligatorios.")
        return None

    return {"auth_token": auth_token, "ct0": ct0}


def load_cookies_from_secret():
    """Carga cookies desde el GitHub Secret TWITTER_COOKIES (base64)."""
    cookies_b64 = os.environ.get("TWITTER_COOKIES")
    if not cookies_b64:
        return False

    try:
        cookies_json = base64.b64decode(cookies_b64).decode("utf-8")
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            f.write(cookies_json)
        print("✅ CI: cookies cargadas desde TWITTER_COOKIES secret.")
        return True
    except Exception as e:
        print(f"⚠️  CI: error decodificando cookies: {e}")
        return False


def export_cookies_for_ci():
    """Muestra el base64 de las cookies para GitHub Secrets."""
    if not os.path.exists(COOKIES_FILE):
        return

    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies_json = f.read()
        cookies_b64 = base64.b64encode(cookies_json.encode("utf-8")).decode("utf-8")

        if CI_MODE:
            # Guardar en GITHUB_OUTPUT para posible uso
            github_output = os.environ.get("GITHUB_OUTPUT")
            if github_output:
                with open(github_output, "a") as f:
                    f.write(f"updated_cookies={cookies_b64}\n")
            print("✅ CI: cookies actualizadas exportadas.")
        else:
            print("\n" + "═" * 60)
            print("  🔑 COOKIES PARA GITHUB ACTIONS")
            print("═" * 60)
            print("  Copiá TODO el texto de abajo y pegalo como GitHub Secret")
            print("  con el nombre: TWITTER_COOKIES\n")
            print("  ── INICIO ──")
            print(cookies_b64)
            print("  ── FIN ──\n")
            print("═" * 60)
    except Exception as e:
        print(f"  ⚠️ No se pudo exportar cookies: {e}")


async def try_login_with_credentials(client, account):
    """Intenta login con credenciales. Retorna True si tuvo éxito."""
    label = account.get("label", account.get("username", "?"))
    print(f"  🔑 Intentando login con cuenta: {label}...", end="", flush=True)

    try:
        await client.login(
            auth_info_1=account["username"],
            auth_info_2=account.get("email", ""),
            password=account["password"],
            cookies_file=COOKIES_FILE
        )
        print(" ✅ OK")
        return True
    except Exception as e:
        err = str(e)
        if "366" in err:
            print(f" ❌ bloqueado por Twitter")
        elif "398" in err:
            print(f" ❌ CAPTCHA detectado")
        elif "429" in err:
            print(f" ❌ rate limited")
        else:
            print(f" ❌ {err[:80]}")
        return False


async def do_login(client, account_mgr, force_new=False):
    """Intenta autenticar con Twitter/X usando múltiples métodos."""

    # ═══ CI MODE ═══
    if CI_MODE:
        # Intento 1: Cookies del secret
        if not force_new and load_cookies_from_secret():
            try:
                client.load_cookies(COOKIES_FILE)
                print("✅ CI: sesión restaurada desde cookies.")
                return True
            except Exception as e:
                print(f"⚠️  CI: cookies expiradas ({e}). Intentando auto-login...")

        # Intento 2: Login con credenciales de secrets
        if account_mgr.has_accounts():
            print(f"🔄 CI: intentando login con {account_mgr.get_account_count()} cuenta(s)...")
            for _ in range(account_mgr.get_account_count()):
                account = account_mgr.get_next_account()
                if await try_login_with_credentials(client, account):
                    # Guardar cookies para próximas ejecuciones
                    export_cookies_for_ci()
                    return True
                await asyncio.sleep(5)

            print("❌ CI: ninguna cuenta pudo loguearse.")

        return False

    # ═══ LOCAL MODE ═══
    if not force_new and os.path.exists(COOKIES_FILE):
        print("\n🍪 Cargando cookies guardadas...")
        try:
            client.load_cookies(COOKIES_FILE)
            print("✅ Sesión restaurada desde cookies.\n")
            return True
        except Exception as e:
            print(f"⚠️  Cookies inválidas ({e}), necesitás loguearte de nuevo.\n")

    if force_new and os.path.exists(COOKIES_FILE):
        os.remove(COOKIES_FILE)
        print("🗑️  Cookies anteriores eliminadas.")

    username, email, password = get_credentials()
    try:
        await client.login(
            auth_info_1=username,
            auth_info_2=email,
            password=password,
            cookies_file=COOKIES_FILE
        )
        print("\n✅ Login exitoso. Cookies guardadas.\n")
        export_cookies_for_ci()
        return True
    except Exception as e:
        error_msg = str(e)
        print(f"\n⚠️  Login con credenciales falló: {error_msg}")

        if "366" in error_msg:
            print("   Twitter bloqueó el flujo de login automatizado.")
        elif "398" in error_msg:
            print("   Twitter detectó actividad no humana (CAPTCHA).")
        else:
            print("   Twitter rechazó la autenticación.")

        print("\n   Probando método alternativo: cookies del navegador...")
        cookies = get_browser_cookies()
        if cookies:
            try:
                client.set_cookies(cookies, clear_cookies=True)
                client.save_cookies(COOKIES_FILE)
                print("  ✅ Cookies del navegador importadas correctamente.\n")
                export_cookies_for_ci()
                return True
            except Exception as e2:
                print(f"  ❌ Error importando cookies: {e2}")

    return False


# ═══════════════════════════════════════════════════════════════
#  ANÁLISIS DE SENTIMIENTO
# ═══════════════════════════════════════════════════════════════

def analyze_sentiment(text):
    """Analiza el sentimiento de un texto."""
    negative_words = [
        "error", "problema", "falla", "no funciona", "caída", "lento",
        "imposible", "frustración", "queja", "demora", "bug", "reclamo",
        "horrible", "pésimo", "desastre", "inútil", "vergüenza", "mal",
        "peor", "molesta", "odio", "bronca", "cansado", "harto",
        "no puedo", "no anda", "se cayó", "no carga", "no sirve",
        "traba", "cuelga", "actualización", "incompatible", "rechazado",
        "vencido", "multa", "intimación", "deuda", "apremio", "eliminar",
        "lastre", "lentisimo", "LPQLP", "carreta", "no funcione",
        "no cambia", "elimine", "feroces", "no tienen bolas", "dinosaurios",
        "robo", "roba", "enano", "privilegios", "mierda", "renegando",
        "Faltan huevos", "Demencial"
    ]
    positive_words = [
        "excelente", "genial", "muy bien", "rápido", "fácil",
        "perfecto", "útil", "práctico", "mejoró", "mejor",
        "bueno", "correcto", "ok"
    ]

    text_lower = text.lower()
    neg_count = sum(1 for w in negative_words if w.lower() in text_lower)
    pos_count = sum(1 for w in positive_words if w.lower() in text_lower)

    try:
        blob = TextBlob(text)
        tb_polarity = blob.sentiment.polarity
    except Exception:
        tb_polarity = 0

    keyword_score = (pos_count - neg_count) * 0.3
    combined_score = keyword_score + (tb_polarity * 0.2)

    if combined_score > 0.05 or pos_count > neg_count:
        return "positivo", round(combined_score, 3)
    elif combined_score < -0.05 or neg_count > pos_count:
        return "negativo", round(combined_score, 3)
    else:
        return "neutro", round(combined_score, 3)


# ═══════════════════════════════════════════════════════════════
#  SCRAPING CON ROTACIÓN DE CUENTAS
# ═══════════════════════════════════════════════════════════════

async def scrape_tweets():
    """Scrapea tweets para cada palabra clave."""
    account_mgr = AccountManager()
    client = Client("es-AR", user_agent=USER_AGENT)

    if not await do_login(client, account_mgr):
        print("\n❌ No se pudo autenticar con Twitter/X.")
        if CI_MODE:
            print("   Opciones:")
            print("   1. Actualizá TWITTER_COOKIES con setup_cookies.py")
            print("   2. Agregá TWITTER_ACCOUNTS con credenciales para auto-login")
            print("   3. Agregá TWITTER_USERNAME + TWITTER_EMAIL + TWITTER_PASSWORD")
        else:
            print("   Verificá credenciales o importá cookies del navegador.")
        sys.exit(1)

    since_date = f"{datetime.now().year}-01-01"
    until_date = datetime.now().strftime("%Y-%m-%d")
    all_data = {
        "generated_at": datetime.now().isoformat(),
        "period": {"from": since_date, "to": until_date},
        "keywords": []
    }

    print("\n" + "═" * 60)
    print("  🔍 BUSCANDO TWEETS")
    if account_mgr.has_accounts() and account_mgr.get_account_count() > 1:
        print(f"  🔄 {account_mgr.get_account_count()} cuentas disponibles para rotación")
    print("═" * 60)

    rate_limit_count = 0  # Contador de rate limits consecutivos

    for i, keyword in enumerate(KEYWORDS):
        print(f"\n  [{i+1}/{len(KEYWORDS)}] Buscando: #{keyword.upper()}", end="", flush=True)

        keyword_data = {
            "keyword": keyword,
            "posts": [],
            "sentiment_summary": {"positivo": 0, "negativo": 0, "neutro": 0},
            "total_found": 0
        }

        try:
            tweet_list = []

            # ── Búsqueda inicial ──
            try:
                tweets = await client.search_tweet(
                    f"{keyword} lang:es since:{since_date} until:{until_date}", "Latest"
                )
                rate_limit_count = 0  # Reset si tuvo éxito
            except Exception as search_err:
                err_str = str(search_err)

                if "401" in err_str:
                    # ── Cookies expiradas: intentar re-login ──
                    print(f" → 401 (sesión expirada)", flush=True)
                    if await do_login(client, account_mgr, force_new=True):
                        tweets = await client.search_tweet(
                            f"{keyword} lang:es since:{since_date} until:{until_date}", "Latest"
                        )
                    else:
                        raise Exception("No se pudo reautenticar tras 401")

                elif "404" in err_str:
                    print(f" → 404, reautenticando...", flush=True)
                    if await do_login(client, account_mgr, force_new=True):
                        tweets = await client.search_tweet(
                            f"{keyword} lang:es since:{since_date} until:{until_date}", "Latest"
                        )
                    else:
                        raise Exception("No se pudo reautenticar tras 404")

                elif "429" in err_str:
                    rate_limit_count += 1

                    # Si hay múltiples cuentas, rotar
                    if account_mgr.has_accounts() and account_mgr.get_account_count() > 1:
                        print(f" → 429, rotando a otra cuenta...", flush=True)
                        client = Client("es-AR", user_agent=USER_AGENT)
                        account = account_mgr.get_next_account()
                        if account and await try_login_with_credentials(client, account):
                            tweets = await client.search_tweet(
                                f"{keyword} lang:es since:{since_date} until:{until_date}", "Latest"
                            )
                            rate_limit_count = 0
                        else:
                            raise Exception("No se pudo rotar cuenta tras 429")
                    else:
                        # Sin cuentas extra: esperar
                        wait_time = min(60 * rate_limit_count, 300)  # Max 5 min
                        print(f" → 429, esperando {wait_time}s...", end="", flush=True)
                        await asyncio.sleep(wait_time)
                        tweets = await client.search_tweet(
                            f"{keyword} lang:es since:{since_date} until:{until_date}", "Latest"
                        )
                else:
                    raise

            # ── Recolectar tweets con paginación ──
            while tweets:
                for tweet in tweets:
                    if len(tweet_list) >= MAX_TWEETS_PER_KEYWORD:
                        break
                    sentiment, score = analyze_sentiment(tweet.text)

                    tweet_info = {
                        "id": tweet.id,
                        "text": tweet.text,
                        "user": tweet.user.name if tweet.user else "Desconocido",
                        "username": tweet.user.screen_name if tweet.user else "unknown",
                        "date": str(tweet.created_at_datetime) if tweet.created_at_datetime else str(tweet.created_at),
                        "sentiment": sentiment,
                        "sentiment_score": score,
                        "likes": tweet.favorite_count or 0,
                        "retweets": tweet.retweet_count or 0,
                        "replies": tweet.reply_count or 0,
                        "url": f"https://x.com/{tweet.user.screen_name}/status/{tweet.id}" if tweet.user else None
                    }
                    tweet_list.append(tweet_info)
                    keyword_data["sentiment_summary"][sentiment] += 1

                print(f" → {len(tweet_list)} tweets...", end="", flush=True)

                if len(tweet_list) >= MAX_TWEETS_PER_KEYWORD:
                    break

                try:
                    tweets = await tweets.next()
                except Exception as page_err:
                    err_str = str(page_err)
                    if "429" in err_str:
                        if account_mgr.has_accounts() and account_mgr.get_account_count() > 1:
                            print(" (429, rotando cuenta...)", end="", flush=True)
                            client = Client("es-AR", user_agent=USER_AGENT)
                            account = account_mgr.get_next_account()
                            if account and await try_login_with_credentials(client, account):
                                try:
                                    tweets = await client.search_tweet(
                                        f"{keyword} lang:es since:{since_date} until:{until_date}", "Latest"
                                    )
                                    continue
                                except Exception:
                                    break
                            else:
                                break
                        else:
                            print(" (429, esperando 60s...)", end="", flush=True)
                            await asyncio.sleep(60)
                            try:
                                tweets = await tweets.next()
                            except Exception:
                                break
                    elif "401" in err_str:
                        print(" (401, reautenticando...)", flush=True)
                        if await do_login(client, account_mgr, force_new=True):
                            try:
                                tweets = await client.search_tweet(
                                    f"{keyword} lang:es since:{since_date} until:{until_date}", "Latest"
                                )
                            except Exception:
                                break
                        else:
                            break
                    elif "404" in err_str:
                        print(" (404, reautenticando...)", flush=True)
                        if await do_login(client, account_mgr, force_new=True):
                            try:
                                tweets = await client.search_tweet(
                                    f"{keyword} lang:es since:{since_date} until:{until_date}", "Latest"
                                )
                            except Exception:
                                break
                        else:
                            break
                    else:
                        break

                await asyncio.sleep(3)

            tweet_list.sort(key=lambda x: x["date"], reverse=True)
            keyword_data["posts"] = tweet_list
            keyword_data["total_found"] = len(tweet_list)

            print(f" → {len(tweet_list)} tweets encontrados ✓")
            s = keyword_data["sentiment_summary"]
            print(f"      Sentimiento: +{s['positivo']} ~{s['neutro']} -{s['negativo']}")

        except Exception as e:
            print(f" → Error: {e}")
            keyword_data["error"] = str(e)

        all_data["keywords"].append(keyword_data)

        if i < len(KEYWORDS) - 1:
            await asyncio.sleep(PAUSE_BETWEEN_KEYWORDS)

    return all_data


def save_data(data):
    """Guarda los datos scrapados en JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    docs_data = os.path.join(OUTPUT_DIR, "tweets_data.json")
    with open(docs_data, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Datos guardados en: {DATA_FILE}")


async def main():
    """Flujo principal de la aplicación."""
    print("\n" + "═" * 60)
    print("  📊 COMARB — Análisis de Sentimiento Twitter/X")
    print("  Sistemas: SIFERE | SIRCAR | SIRPEI | SIRCREB | SIRCUPA | SIRTAC")
    if CI_MODE:
        print("  🤖 Modo: GitHub Actions (CI)")
    else:
        print("  💻 Modo: Local")
    print("═" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Scraping
    data = await scrape_tweets()

    # 2. Guardar datos
    save_data(data)

    # 3. Generar reporte HTML
    print("\n" + "═" * 60)
    print("  📄 GENERANDO REPORTE HTML")
    print("═" * 60)
    generate_html_report(data, REPORT_FILE)

    # 4. Resumen final
    total_tweets = sum(k["total_found"] for k in data["keywords"])
    total_pos = sum(k["sentiment_summary"]["positivo"] for k in data["keywords"])
    total_neg = sum(k["sentiment_summary"]["negativo"] for k in data["keywords"])
    total_neu = sum(k["sentiment_summary"]["neutro"] for k in data["keywords"])

    print("\n" + "═" * 60)
    print("  ✅ RESUMEN FINAL")
    print("═" * 60)
    print(f"  📝 Total tweets encontrados: {total_tweets}")
    print(f"  😊 Positivos: {total_pos}")
    print(f"  😐 Neutros: {total_neu}")
    print(f"  😠 Negativos: {total_neg}")
    print(f"\n  📄 Reporte HTML: {os.path.abspath(REPORT_FILE)}")
    print(f"  💾 Datos JSON:   {os.path.abspath(DATA_FILE)}")

    if CI_MODE:
        print(f"\n  🌐 El reporte se publicará en GitHub Pages automáticamente.")
    else:
        print(f"\n  Abrí el archivo HTML en tu navegador para ver el dashboard.")
    print("═" * 60 + "\n")

    if not CI_MODE:
        try:
            import webbrowser
            webbrowser.open(f"file://{os.path.abspath(REPORT_FILE)}")
            print("  🌐 Abriendo reporte en el navegador...\n")
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())

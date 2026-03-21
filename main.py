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

# ── Parche para twikit: corrige regex de X.com (formato webpack actual) ──
def _patch_twikit_transaction():
    """
    Twitter/X cambió el formato HTML donde se referencia ondemand.s.
    Formato viejo: "ondemand.s":"<hash>"
    Formato actual: 20113:"ondemand.s" (nombre) + 20113:"<hash>" (hash aparte)
    twikit 2.3.x no lo soporta, este parche corrige los regex en runtime.
    """
    try:
        import re
        import twikit.x_client_transaction.transaction as txn
        # Solo parchear si tiene el regex viejo o el formato con corchetes
        current = txn.ON_DEMAND_FILE_REGEX.pattern
        if '["ondemand' in current or '"ondemand.s":"' in current:
            txn.ON_DEMAND_FILE_REGEX = re.compile(
                r'(\d+):"ondemand\.s"', flags=(re.VERBOSE | re.MULTILINE))
            txn.ON_DEMAND_HASH_PATTERN = r',{}:"([0-9a-f]+)"'
            txn.INDICES_REGEX = re.compile(
                r'\[(\d+)\],\s*16', flags=(re.VERBOSE | re.MULTILINE))

            # Parchear get_indices para usar el nuevo formato de 2 pasos
            async def _patched_get_indices(self, home_page_response, session, headers):
                key_byte_indices = []
                response = self.validate_response(home_page_response) or self.home_page_response
                response_str = str(response)
                on_demand_file = txn.ON_DEMAND_FILE_REGEX.search(response_str)
                if on_demand_file:
                    numeric_index = on_demand_file.group(1)
                    hash_pattern = re.compile(txn.ON_DEMAND_HASH_PATTERN.format(numeric_index))
                    hash_match = hash_pattern.search(response_str)
                    if hash_match:
                        on_demand_hash = hash_match.group(1)
                        url = f"https://abs.twimg.com/responsive-web/client-web/ondemand.s.{on_demand_hash}a.js"
                        resp = await session.request(method="GET", url=url, headers=headers)
                        for item in txn.INDICES_REGEX.finditer(str(resp.text)):
                            key_byte_indices.append(item.group(1))
                if not key_byte_indices:
                    raise Exception("Couldn't get KEY_BYTE indices")
                key_byte_indices = list(map(int, key_byte_indices))
                return key_byte_indices[0], key_byte_indices[1:]

            txn.ClientTransaction.get_indices = _patched_get_indices
            if not CI_MODE:
                print("🔧 Parche twikit aplicado (regex ondemand.s actualizado).")
    except Exception as e:
        print(f"⚠️  No se pudo aplicar parche twikit: {e}")

_patch_twikit_transaction()

# ── Configuración ──
KEYWORDS = ["comarb", "sifere", "sircar", "sirpei", "sircreb", "sircupa", "sirtac"]
MAX_TWEETS_PER_KEYWORD = 200
COOKIES_FILE = "twitter_cookies.json"
MULTI_COOKIES_FILE = "twitter_multi_cookies.json"
DATA_FILE = "tweets_data.json"
REPORT_FILE = os.path.join(OUTPUT_DIR, "index.html")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
PAUSE_BETWEEN_KEYWORDS = 30


# ═══════════════════════════════════════════════════════════════
#  DICCIONARIOS DE EMOJIS PARA SENTIMIENTO
# ═══════════════════════════════════════════════════════════════

# Peso: cada emoji cuenta como N palabras positivas/negativas
POSITIVE_EMOJIS = {
    # Caras felices
    "😀": 1, "😃": 1, "😄": 1, "😁": 1, "😆": 1, "😊": 1, "🥰": 1.5,
    "😍": 1.5, "🤩": 1.5, "☺️": 1, "😉": 0.5, "😋": 0.5, "😎": 1,
    "🥳": 1.5, "😏": 0.3, "🙂": 0.5, "😌": 0.5, "🤗": 1, "😇": 1,
    # Gestos positivos
    "👍": 1, "👏": 1, "🙌": 1.5, "🤝": 1, "✌️": 0.5, "🤞": 0.5,
    "💪": 1, "👌": 1, "🫡": 0.5,
    # Corazones y amor
    "❤️": 1.5, "🧡": 1, "💛": 1, "💚": 1, "💙": 1, "💜": 1,
    "🖤": 0.5, "🤍": 0.5, "💕": 1.5, "💖": 1.5, "💗": 1, "💘": 1,
    "💝": 1.5, "❤️‍🔥": 1.5, "♥️": 1,
    # Celebración
    "🎉": 1.5, "🎊": 1.5, "🎆": 1, "🎇": 1, "✨": 1, "🌟": 1,
    "⭐": 1, "🏆": 1.5, "🥇": 1.5, "🎯": 1, "🏅": 1,
    # Risa
    "😂": 1, "🤣": 1, "😹": 1,
    # Aprobación / OK
    "✅": 1, "✔️": 1, "🆗": 0.5, "💯": 1.5, "🔝": 1,
    # Otros positivos
    "🚀": 1, "💡": 0.5, "🙏": 1, "🌈": 0.5, "☀️": 0.5,
    "🌻": 0.5, "🎶": 0.5, "💐": 1, "🌹": 1,
}

NEGATIVE_EMOJIS = {
    # Caras tristes / enojadas
    "😢": 1, "😭": 1.5, "😞": 1, "😔": 1, "😟": 1, "🙁": 1,
    "☹️": 1, "😣": 1, "😖": 1, "😫": 1.5, "😩": 1.5, "🥺": 0.5,
    "😤": 1.5, "😡": 2, "🤬": 2.5, "😠": 1.5, "🤢": 1, "🤮": 1.5,
    "😰": 1, "😨": 1, "😱": 1.5, "😵": 1, "😵‍💫": 1, "🥴": 0.5,
    "😷": 0.5, "🤒": 0.5, "🤕": 0.5, "😑": 0.5, "😒": 1,
    "🙄": 1, "😪": 0.5, "😮‍💨": 1, "💀": 1, "☠️": 1, "🤡": 1.5,
    # Gestos negativos
    "👎": 1.5, "🖕": 2, "🤦": 1, "🤦‍♂️": 1, "🤦‍♀️": 1,
    # Símbolos negativos
    "❌": 1.5, "⛔": 1, "🚫": 1, "❗": 0.5, "‼️": 1, "⚠️": 0.5,
    "🔴": 0.5, "💔": 1.5, "🩹": 0.5, "📉": 1,
    # Otros negativos
    "🗑️": 1, "💩": 1.5, "🤷": 0.5, "🤷‍♂️": 0.5, "🤷‍♀️": 0.5,
    "😬": 0.5, "🫠": 0.5, "🫤": 0.5, "😶": 0.3,
    # Fuego (puede ser negativo en contexto de queja)
    "🔥": 0.3,
}


def count_emojis(text):
    """
    Cuenta emojis positivos y negativos en un texto.
    Retorna (pos_score, neg_score, emoji_details).
    """
    pos_score = 0.0
    neg_score = 0.0
    found_emojis = []

    for emoji, weight in POSITIVE_EMOJIS.items():
        count = text.count(emoji)
        if count > 0:
            pos_score += weight * count
            found_emojis.append({"emoji": emoji, "type": "positivo", "count": count})

    for emoji, weight in NEGATIVE_EMOJIS.items():
        count = text.count(emoji)
        if count > 0:
            neg_score += weight * count
            found_emojis.append({"emoji": emoji, "type": "negativo", "count": count})

    return pos_score, neg_score, found_emojis


# ═══════════════════════════════════════════════════════════════
#  ANÁLISIS DE SENTIMIENTO (con emojis)
# ═══════════════════════════════════════════════════════════════

def analyze_sentiment(text):
    """
    Analiza el sentimiento de un texto combinando:
    1. Diccionario de palabras en español
    2. Diccionario de emojis con pesos
    3. TextBlob (polarity en inglés como complemento)

    Retorna: (sentimiento, score, detalles_emojis)
    """
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

    # ── 1. Palabras clave ──
    neg_word_count = sum(1 for w in negative_words if w.lower() in text_lower)
    pos_word_count = sum(1 for w in positive_words if w.lower() in text_lower)

    # ── 2. Emojis ──
    emoji_pos, emoji_neg, emoji_details = count_emojis(text)

    # ── 3. TextBlob ──
    try:
        blob = TextBlob(text)
        tb_polarity = blob.sentiment.polarity
    except Exception:
        tb_polarity = 0

    # ── Score combinado (ponderado) ──
    # Palabras:  peso 0.30 por match
    # Emojis:    peso 0.25 por unidad de score
    # TextBlob:  peso 0.20 del polarity
    word_score = (pos_word_count - neg_word_count) * 0.30
    emoji_score = (emoji_pos - emoji_neg) * 0.25
    tb_score = tb_polarity * 0.20

    combined_score = word_score + emoji_score + tb_score

    # Totales para comparación
    total_pos = pos_word_count + emoji_pos
    total_neg = neg_word_count + emoji_neg

    if combined_score > 0.05 or total_pos > total_neg:
        sentiment = "positivo"
    elif combined_score < -0.05 or total_neg > total_pos:
        sentiment = "negativo"
    else:
        sentiment = "neutro"

    return sentiment, round(combined_score, 3), emoji_details


# ═══════════════════════════════════════════════════════════════
#  GESTIÓN DE CUENTAS MÚLTIPLES
# ═══════════════════════════════════════════════════════════════

class AccountManager:
    """Gestiona múltiples cuentas de Twitter para rotación."""

    def __init__(self):
        self.accounts = []
        self.current_index = 0
        self.clients = {}
        self._load_accounts()

    def _load_accounts(self):
        if CI_MODE:
            self._load_accounts_ci()

    def _load_accounts_ci(self):
        accounts_json = os.environ.get("TWITTER_ACCOUNTS")
        if accounts_json:
            try:
                try:
                    decoded = base64.b64decode(accounts_json).decode("utf-8")
                    self.accounts = json.loads(decoded)
                except Exception:
                    self.accounts = json.loads(accounts_json)
                print(f"✅ CI: {len(self.accounts)} cuentas cargadas desde TWITTER_ACCOUNTS")
                random.shuffle(self.accounts)
                return
            except Exception as e:
                print(f"⚠️  CI: error parseando TWITTER_ACCOUNTS: {e}")

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
    if not os.path.exists(COOKIES_FILE):
        return
    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies_json = f.read()
        cookies_b64 = base64.b64encode(cookies_json.encode("utf-8")).decode("utf-8")

        if CI_MODE:
            github_output = os.environ.get("GITHUB_OUTPUT")
            if github_output:
                with open(github_output, "a") as f:
                    f.write(f"updated_cookies={cookies_b64}\n")
            print("✅ CI: cookies actualizadas exportadas.")
        else:
            print("\n" + "═" * 60)
            print("  🔑 COOKIES PARA GITHUB ACTIONS")
            print("═" * 60)
            print("  Copiá TODO el texto de abajo como GitHub Secret: TWITTER_COOKIES\n")
            print("  ── INICIO ──")
            print(cookies_b64)
            print("  ── FIN ──\n")
            print("═" * 60)
    except Exception as e:
        print(f"  ⚠️ No se pudo exportar cookies: {e}")


async def try_login_with_credentials(client, account):
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
            print(f" ❌ bloqueado")
        elif "398" in err:
            print(f" ❌ CAPTCHA")
        elif "429" in err:
            print(f" ❌ rate limited")
        else:
            print(f" ❌ {err[:80]}")
        return False


async def do_login(client, account_mgr, force_new=False):
    # ═══ CI MODE ═══
    if CI_MODE:
        if not force_new and load_cookies_from_secret():
            try:
                client.load_cookies(COOKIES_FILE)
                print("✅ CI: sesión restaurada desde cookies.")
                return True
            except Exception as e:
                print(f"⚠️  CI: cookies expiradas ({e}). Intentando auto-login...")

        if account_mgr.has_accounts():
            print(f"🔄 CI: intentando login con {account_mgr.get_account_count()} cuenta(s)...")
            for _ in range(account_mgr.get_account_count()):
                account = account_mgr.get_next_account()
                if await try_login_with_credentials(client, account):
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
#  MULTI-CUENTA: cargar cookies y crear clientes
# ═══════════════════════════════════════════════════════════════

def load_multi_cookies_from_secret():
    """
    Carga cookies desde TWITTER_COOKIES secret.
    Soporta dos formatos:
    - Multi-cuenta: {"multi": true, "accounts": [...]}
    - Cuenta única (legacy): contenido directo del cookies.json
    Retorna lista de {"username": str, "cookies": dict} o None.
    """
    cookies_b64 = os.environ.get("TWITTER_COOKIES")
    if not cookies_b64:
        return None
    try:
        cookies_json = base64.b64decode(cookies_b64).decode("utf-8")
        data = json.loads(cookies_json)

        # Formato multi-cuenta
        if isinstance(data, dict) and data.get("multi"):
            accounts = data.get("accounts", [])
            if accounts:
                print(f"✅ CI: {len(accounts)} cuenta(s) cargadas desde TWITTER_COOKIES (multi).")
                return accounts

        # Formato legacy (cuenta única) — wrappear en lista
        print("✅ CI: 1 cuenta cargada desde TWITTER_COOKIES (legacy).")
        return [{"username": "default", "cookies": data}]

    except Exception as e:
        print(f"⚠️  CI: error parseando TWITTER_COOKIES: {e}")
        return None


def create_client():
    """Crea un Client de twikit. La inicialización de client_transaction se hace automáticamente."""
    return Client("es-AR", user_agent=USER_AGENT)


async def setup_multi_clients(cookie_accounts):
    """
    Crea un Client de twikit por cada cuenta con cookies.
    Retorna lista de (Client, username) para las que funcionaron.
    """
    clients = []
    for acc in cookie_accounts:
        username = acc["username"]
        client = create_client()
        try:
            # Cargar cookies directamente con set_cookies
            client.set_cookies(acc["cookies"], clear_cookies=True)
            clients.append({"client": client, "username": username, "cookies_data": acc["cookies"]})
            print(f"  ✅ @{username} — sesión cargada")
        except Exception as e:
            print(f"  ❌ @{username} — error: {e}")
    return clients


def save_multi_cookies(clients_info):
    """
    Re-guarda las cookies de todos los clientes al formato multi-cuenta.
    Retorna el JSON para actualizar el secret.
    """
    accounts = []
    for info in clients_info:
        client = info["client"]
        username = info["username"]
        try:
            tmp_file = f"_tmp_cookies_{username}.json"
            client.save_cookies(tmp_file)
            with open(tmp_file, "r", encoding="utf-8") as f:
                cookies_data = json.load(f)
            os.remove(tmp_file)
            accounts.append({"username": username, "cookies": cookies_data})
        except Exception as e:
            print(f"  ⚠️ No se pudieron guardar cookies de @{username}: {e}")
            # Mantener las cookies originales
            accounts.append({"username": username, "cookies": info.get("cookies_data", {})})

    data = {"multi": True, "accounts": accounts}

    # Guardar como archivo JSON (para que el workflow lo re-suba)
    with open(MULTI_COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    # También guardar en formato legacy para compatibilidad
    if len(accounts) == 1:
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts[0]["cookies"], f, ensure_ascii=False)
    else:
        # Guardar el JSON multi completo como COOKIES_FILE para el workflow
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    print(f"  🍪 Cookies re-guardadas para {len(accounts)} cuenta(s).")


# ═══════════════════════════════════════════════════════════════
#  SCRAPING
# ═══════════════════════════════════════════════════════════════

async def search_keyword_with_client(client, keyword, since_date, until_date):
    """Busca un keyword con un client específico. Retorna keyword_data."""
    keyword_data = {
        "keyword": keyword,
        "posts": [],
        "sentiment_summary": {"positivo": 0, "negativo": 0, "neutro": 0},
        "emoji_stats": {"total_positive_emojis": 0, "total_negative_emojis": 0, "top_emojis": {}},
        "total_found": 0
    }

    try:
        tweet_list = []
        all_emoji_counter = {}

        tweets = await client.search_tweet(
            f"{keyword} lang:es since:{since_date} until:{until_date}", "Latest"
        )

        while tweets:
            for tweet in tweets:
                if len(tweet_list) >= MAX_TWEETS_PER_KEYWORD:
                    break

                sentiment, score, emoji_details = analyze_sentiment(tweet.text)

                for ed in emoji_details:
                    emoji = ed["emoji"]
                    all_emoji_counter[emoji] = all_emoji_counter.get(emoji, 0) + ed["count"]
                    if ed["type"] == "positivo":
                        keyword_data["emoji_stats"]["total_positive_emojis"] += ed["count"]
                    else:
                        keyword_data["emoji_stats"]["total_negative_emojis"] += ed["count"]

                tweet_info = {
                    "id": tweet.id,
                    "text": tweet.text,
                    "user": tweet.user.name if tweet.user else "Desconocido",
                    "username": tweet.user.screen_name if tweet.user else "unknown",
                    "date": str(tweet.created_at_datetime) if tweet.created_at_datetime else str(tweet.created_at),
                    "sentiment": sentiment,
                    "sentiment_score": score,
                    "emojis_found": emoji_details,
                    "likes": tweet.favorite_count or 0,
                    "retweets": tweet.retweet_count or 0,
                    "replies": tweet.reply_count or 0,
                    "url": f"https://x.com/{tweet.user.screen_name}/status/{tweet.id}" if tweet.user else None
                }
                tweet_list.append(tweet_info)
                keyword_data["sentiment_summary"][sentiment] += 1

            print(f" → {len(tweet_list)}...", end="", flush=True)

            if len(tweet_list) >= MAX_TWEETS_PER_KEYWORD:
                break

            try:
                tweets = await tweets.next()
            except Exception as page_err:
                err_str = str(page_err)
                if "429" in err_str:
                    print(" (429, esperando 60s...)", end="", flush=True)
                    await asyncio.sleep(60)
                    try:
                        tweets = await tweets.next()
                    except Exception:
                        break
                else:
                    break

            await asyncio.sleep(3)

        tweet_list.sort(key=lambda x: x["date"], reverse=True)
        keyword_data["posts"] = tweet_list
        keyword_data["total_found"] = len(tweet_list)

        top_emojis = sorted(all_emoji_counter.items(), key=lambda x: x[1], reverse=True)[:10]
        keyword_data["emoji_stats"]["top_emojis"] = dict(top_emojis)

        print(f" → {len(tweet_list)} tweets ✓")
        s = keyword_data["sentiment_summary"]
        es = keyword_data["emoji_stats"]
        print(f"      Sentimiento: +{s['positivo']} ~{s['neutro']} -{s['negativo']}")
        if es["total_positive_emojis"] or es["total_negative_emojis"]:
            top_3 = " ".join([e for e, _ in top_emojis[:5]])
            print(f"      Emojis: 😊{es['total_positive_emojis']} 😡{es['total_negative_emojis']}  Top: {top_3}")

    except Exception as e:
        print(f" → Error: {e}")
        keyword_data["error"] = str(e)

    return keyword_data


async def scrape_tweets():
    """Scraping principal con distribución de keywords entre cuentas."""

    # ── Intentar cargar multi-cuenta ──
    clients_info = []
    if CI_MODE:
        cookie_accounts = load_multi_cookies_from_secret()
        if cookie_accounts:
            clients_info = await setup_multi_clients(cookie_accounts)

    # ── Fallback: cuenta única (legacy) ──
    if not clients_info:
        account_mgr = AccountManager()
        client = create_client()

        if not await do_login(client, account_mgr):
            print("\n❌ No se pudo autenticar con Twitter/X.")
            if CI_MODE:
                print("   Revisá el secret TWITTER_COOKIES.")
                print("   Ejecutá setup_cookies.py localmente para regenerarlo.")
            else:
                print("   Verificá credenciales o importá cookies del navegador.")
            sys.exit(1)

        clients_info = [{"client": client, "username": "default", "cookies_data": {}}]

    since_date = f"{datetime.now().year}-01-01"
    until_date = datetime.now().strftime("%Y-%m-%d")
    all_data = {
        "generated_at": datetime.now().isoformat(),
        "period": {"from": since_date, "to": until_date},
        "keywords": []
    }

    n_clients = len(clients_info)

    print("\n" + "═" * 60)
    print("  🔍 BUSCANDO TWEETS")
    if n_clients > 1:
        print(f"  🔄 {n_clients} cuentas — keywords distribuidas:")
        for i, kw in enumerate(KEYWORDS):
            acc = clients_info[i % n_clients]
            print(f"     {kw.upper()} → @{acc['username']}")
    print("═" * 60)

    for i, keyword in enumerate(KEYWORDS):
        info = clients_info[i % n_clients]
        client = info["client"]
        label = f"@{info['username']}" if info["username"] != "default" else ""

        print(f"\n  [{i+1}/{len(KEYWORDS)}] Buscando: #{keyword.upper()}{' (' + label + ')' if label else ''}", end="", flush=True)

        keyword_data = await search_keyword_with_client(client, keyword, since_date, until_date)
        all_data["keywords"].append(keyword_data)

        if i < len(KEYWORDS) - 1:
            await asyncio.sleep(PAUSE_BETWEEN_KEYWORDS)

    # ── Re-guardar cookies al final ──
    if n_clients > 0:
        save_multi_cookies(clients_info)

    return all_data


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    docs_data = os.path.join(OUTPUT_DIR, "tweets_data.json")
    with open(docs_data, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Datos guardados en: {DATA_FILE}")


async def main():
    print("\n" + "═" * 60)
    print("  📊 COMARB — Análisis de Sentimiento Twitter/X")
    print("  Sistemas: SIFERE | SIRCAR | SIRPEI | SIRCREB | SIRCUPA | SIRTAC")
    if CI_MODE:
        print("  🤖 Modo: GitHub Actions (CI)")
    else:
        print("  💻 Modo: Local")
    print("═" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    data = await scrape_tweets()
    save_data(data)

    print("\n" + "═" * 60)
    print("  📄 GENERANDO REPORTE HTML")
    print("═" * 60)
    generate_html_report(data, REPORT_FILE)

    total_tweets = sum(k["total_found"] for k in data["keywords"])
    total_pos = sum(k["sentiment_summary"]["positivo"] for k in data["keywords"])
    total_neg = sum(k["sentiment_summary"]["negativo"] for k in data["keywords"])
    total_neu = sum(k["sentiment_summary"]["neutro"] for k in data["keywords"])
    total_emoji_pos = sum(k.get("emoji_stats", {}).get("total_positive_emojis", 0) for k in data["keywords"])
    total_emoji_neg = sum(k.get("emoji_stats", {}).get("total_negative_emojis", 0) for k in data["keywords"])

    print("\n" + "═" * 60)
    print("  ✅ RESUMEN FINAL")
    print("═" * 60)
    print(f"  📝 Total tweets encontrados: {total_tweets}")
    print(f"  😊 Positivos: {total_pos}")
    print(f"  😐 Neutros: {total_neu}")
    print(f"  😠 Negativos: {total_neg}")
    print(f"  🎭 Emojis detectados: {total_emoji_pos} positivos, {total_emoji_neg} negativos")
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

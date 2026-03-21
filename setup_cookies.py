#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  Herramienta de configuración multi-cuenta para GitHub Actions
  Genera cookies de MÚLTIPLES cuentas de Twitter/X
  para distribuir la búsqueda y reducir rate limits.
═══════════════════════════════════════════════════════════════

  Ejecutá este script localmente para:
  1. Agregar cookies de 2-3 cuentas de Twitter/X
  2. Verificar que funcionan
  3. Obtener el base64 para el GitHub Secret TWITTER_COOKIES

  Uso:  python setup_cookies.py
═══════════════════════════════════════════════════════════════
"""

import asyncio
import base64
import json
import os
import sys


def create_client():
    return Client("es-AR", user_agent=USER_AGENT)

def install_twikit():
    try:
        import twikit
    except ImportError:
        print("📦 Instalando twikit...")
        os.system(f"{sys.executable} -m pip install twikit --upgrade -q")

install_twikit()

from twikit import Client

# ── Parche para twikit: corrige regex de X.com (formato webpack actual) ──
def _patch_twikit_transaction():
    try:
        import re
        import twikit.x_client_transaction.transaction as txn
        current = txn.ON_DEMAND_FILE_REGEX.pattern
        if '["ondemand' in current or '"ondemand.s":"' in current:
            txn.ON_DEMAND_FILE_REGEX = re.compile(
                r'(\d+):"ondemand\.s"', flags=(re.VERBOSE | re.MULTILINE))
            txn.ON_DEMAND_HASH_PATTERN = r',{}:"([0-9a-f]+)"'
            txn.INDICES_REGEX = re.compile(
                r'\[(\d+)\],\s*16', flags=(re.VERBOSE | re.MULTILINE))

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
            print("  🔧 Parche twikit aplicado.")
    except Exception as e:
        print(f"  ⚠️  No se pudo aplicar parche twikit: {e}")

_patch_twikit_transaction()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
MULTI_COOKIES_FILE = "twitter_multi_cookies.json"


def load_existing():
    """Carga la estructura multi-cuenta existente si existe."""
    if os.path.exists(MULTI_COOKIES_FILE):
        with open(MULTI_COOKIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"multi": True, "accounts": []}


def save_multi(data):
    """Guarda la estructura multi-cuenta."""
    with open(MULTI_COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def show_accounts(data):
    """Muestra las cuentas configuradas."""
    if not data["accounts"]:
        print("  (vacío — no hay cuentas configuradas)")
        return
    for i, acc in enumerate(data["accounts"], 1):
        print(f"  [{i}] @{acc['username']}")


async def add_account(data):
    """Agrega una cuenta usando cookies del navegador."""
    print()
    print("  Para obtener las cookies:")
    print("  1. Abrí Twitter/X en tu navegador y logueate con la cuenta")
    print("  2. Presioná F12 → Application → Cookies → https://x.com")
    print("  3. Buscá 'auth_token' y 'ct0' y copiá sus valores")
    print()

    username = input("  👤 Usuario de Twitter (sin @): ").strip()
    if not username:
        print("  ❌ Usuario requerido.")
        return

    # Verificar si ya existe
    existing = [a for a in data["accounts"] if a["username"] == username]
    if existing:
        replace = input(f"  ⚠️  @{username} ya existe. ¿Reemplazar? (s/n): ").strip().lower()
        if replace not in ("s", "si", "sí", "y", "yes"):
            return
        data["accounts"] = [a for a in data["accounts"] if a["username"] != username]

    auth_token = input("  🔑 auth_token: ").strip()
    ct0 = input("  🔑 ct0: ").strip()

    if not auth_token or not ct0:
        print("  ❌ Ambos valores (auth_token y ct0) son obligatorios.")
        return

    # Crear un Client temporal para guardar cookies en el formato de twikit
    client = create_client()
    try:
        client.set_cookies({"auth_token": auth_token, "ct0": ct0}, clear_cookies=True)

        # Guardar cookies a archivo temporal y leer el contenido
        tmp_file = f"_tmp_cookies_{username}.json"
        client.save_cookies(tmp_file)
        with open(tmp_file, "r", encoding="utf-8") as f:
            cookies_content = json.load(f)
        os.remove(tmp_file)

        data["accounts"].append({
            "username": username,
            "cookies": cookies_content
        })
        save_multi(data)
        print(f"\n  ✅ @{username} agregado.")
    except Exception as e:
        print(f"\n  ❌ Error: {e}")


async def verify_accounts(data):
    """Verifica cada cuenta con una búsqueda de prueba."""
    if not data["accounts"]:
        print("  No hay cuentas para verificar.")
        return

    print()
    for acc in data["accounts"]:
        print(f"  🔍 Verificando @{acc['username']}...", end="", flush=True)
        client = create_client()
        try:
            # Cargar cookies directamente con set_cookies
            client.set_cookies(acc["cookies"], clear_cookies=True)

            # Hacer una búsqueda de prueba
            tweets = await client.search_tweet("test lang:es", "Latest")
            count = len(tweets) if tweets else 0
            print(f" ✅ OK ({count} tweets)")
        except Exception as e:
            err = str(e)[:60]
            print(f" ❌ {err}")
            if "401" in err:
                print(f"       → Cookies expiradas. Agregá cookies nuevas para @{acc['username']}.")


def remove_account(data):
    """Elimina una cuenta."""
    if not data["accounts"]:
        print("  No hay cuentas para eliminar.")
        return

    show_accounts(data)
    try:
        idx = int(input("\n  Número de cuenta a eliminar: ").strip()) - 1
        if 0 <= idx < len(data["accounts"]):
            removed = data["accounts"].pop(idx)
            save_multi(data)
            print(f"  🗑️  @{removed['username']} eliminado.")
        else:
            print("  ❌ Número inválido.")
    except ValueError:
        print("  ❌ Ingresá un número.")


def export_for_github(data):
    """Exporta todas las cookies como base64 para GitHub Secret."""
    if not data["accounts"]:
        print("  ❌ No hay cuentas. Agregá al menos una antes de exportar.")
        return False

    multi_json = json.dumps(data, ensure_ascii=False)
    multi_b64 = base64.b64encode(multi_json.encode("utf-8")).decode("utf-8")

    print("\n" + "═" * 60)
    print("  ✅ COOKIES MULTI-CUENTA LISTAS PARA GITHUB")
    print("═" * 60)
    print()
    print(f"  📊 {len(data['accounts'])} cuenta(s) configuradas:")
    for acc in data["accounts"]:
        print(f"     • @{acc['username']}")
    print()
    print("  Seguí estos pasos:")
    print()
    print("  1. Andá a tu repositorio en GitHub")
    print("  2. Settings → Secrets and variables → Actions")
    print("  3. Clic en 'New repository secret' (o editá el existente)")
    print("  4. Name: TWITTER_COOKIES")
    print("  5. Value: pegá TODO el contenido de cookies_secret.txt")
    print()

    b64_file = "cookies_secret.txt"
    with open(b64_file, "w") as f:
        f.write(multi_b64)

    print(f"  💾 Secret guardado en: {b64_file}")
    print(f"     ({len(multi_b64)} caracteres)")
    print()
    print("  ⚠️  IMPORTANTE:")
    print("     - No compartas este archivo con nadie.")
    print("     - Las 7 keywords se van a distribuir entre las cuentas:")

    keywords = ["comarb", "sifere", "sircar", "sirpei", "sircreb", "sircupa", "sirtac"]
    n = len(data["accounts"])
    for i, kw in enumerate(keywords):
        acc = data["accounts"][i % n]
        print(f"       {kw.upper()} → @{acc['username']}")

    print()
    print("     - El workflow auto-actualiza las cookies después de cada run.")
    print("═" * 60 + "\n")
    return True


async def main():
    print("\n" + "═" * 60)
    print("  🔧 CONFIGURACIÓN MULTI-CUENTA — Twitter/X")
    print("═" * 60)
    print()
    print("  Configurá 2-3 cuentas de Twitter/X para distribuir")
    print("  las 7 palabras clave entre ellas y reducir rate limits.")
    print("  Cada cuenta buscará ~2-3 keywords.")
    print()

    data = load_existing()

    while True:
        print("\n" + "─" * 40)
        print("  CUENTAS CONFIGURADAS:")
        show_accounts(data)
        print("─" * 40)
        print()
        print("  [1] Agregar cuenta (con cookies del navegador)")
        print("  [2] Verificar cuentas (búsqueda de prueba)")
        print("  [3] Eliminar cuenta")
        print("  [4] Exportar para GitHub Actions y salir")
        print("  [5] Salir sin exportar")
        print()

        choice = input("  Opción: ").strip()

        if choice == "1":
            await add_account(data)
        elif choice == "2":
            await verify_accounts(data)
        elif choice == "3":
            remove_account(data)
        elif choice == "4":
            if export_for_github(data):
                break
        elif choice == "5":
            print("\n  👋 Saliendo.\n")
            break
        else:
            print("  ❌ Opción no válida.")


if __name__ == "__main__":
    asyncio.run(main())

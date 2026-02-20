#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  Herramienta de configuración para GitHub Actions
  Genera las cookies de Twitter y las prepara como Secret
═══════════════════════════════════════════════════════════════

  Ejecutá este script UNA VEZ localmente para:
  1. Loguearte en Twitter/X
  2. Obtener el texto base64 de tus cookies
  3. Pegarlo como GitHub Secret

  Uso:  python setup_cookies.py
═══════════════════════════════════════════════════════════════
"""

import asyncio
import base64
import json
import os
import sys

def install_twikit():
    try:
        import twikit
    except ImportError:
        print("📦 Instalando twikit...")
        os.system(f"{sys.executable} -m pip install twikit --upgrade -q")

install_twikit()

from twikit import Client

COOKIES_FILE = "twitter_cookies.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


async def main():
    print("\n" + "═" * 60)
    print("  🔧 CONFIGURACIÓN DE COOKIES PARA GITHUB ACTIONS")
    print("═" * 60)
    print()
    print("  Este script te va a ayudar a generar las cookies")
    print("  de Twitter/X para que GitHub Actions pueda ejecutar")
    print("  el scraping automáticamente.")
    print()

    client = Client("es-AR", user_agent=USER_AGENT)

    # ── Verificar cookies existentes ──
    if os.path.exists(COOKIES_FILE):
        print("  🍪 Se encontró twitter_cookies.json existente.")
        print()
        use_existing = input("  ¿Usar las cookies existentes? (s/n): ").strip().lower()
        if use_existing in ("s", "si", "sí", "y", "yes", ""):
            try:
                client.load_cookies(COOKIES_FILE)
                print("  ✅ Cookies válidas.")
                export_cookies()
                return
            except Exception:
                print("  ⚠️  Cookies inválidas, necesitás loguearte de nuevo.\n")

    # ── Elegir método ──
    print()
    print("  Elegí cómo loguearte:")
    print("  [1] Usuario + contraseña")
    print("  [2] Cookies del navegador (auth_token + ct0)")
    print()
    choice = input("  Opción (1 o 2): ").strip()

    if choice == "2":
        print()
        print("  Para obtener las cookies:")
        print("  1. Abrí Twitter/X en tu navegador y logueate")
        print("  2. Presioná F12 → Application → Cookies → https://x.com")
        print("  3. Buscá 'auth_token' y 'ct0' y copiá sus valores")
        print()

        auth_token = input("  🔑 auth_token: ").strip()
        ct0 = input("  🔑 ct0: ").strip()

        if not auth_token or not ct0:
            print("  ❌ Ambos valores son obligatorios.")
            sys.exit(1)

        try:
            client.set_cookies({"auth_token": auth_token, "ct0": ct0}, clear_cookies=True)
            client.save_cookies(COOKIES_FILE)
            print("\n  ✅ Cookies guardadas correctamente.")
        except Exception as e:
            print(f"\n  ❌ Error: {e}")
            sys.exit(1)
    else:
        print()
        username = input("  👤 Usuario de Twitter (sin @): ").strip()
        email = input("  📧 Email: ").strip()
        password = input("  🔑 Contraseña: ").strip()

        try:
            await client.login(
                auth_info_1=username,
                auth_info_2=email,
                password=password,
                cookies_file=COOKIES_FILE
            )
            print("\n  ✅ Login exitoso. Cookies guardadas.")
        except Exception as e:
            print(f"\n  ⚠️  Login falló: {e}")
            print("  Intentando con cookies del navegador...\n")

            auth_token = input("  🔑 auth_token: ").strip()
            ct0 = input("  🔑 ct0: ").strip()

            if auth_token and ct0:
                try:
                    client.set_cookies({"auth_token": auth_token, "ct0": ct0}, clear_cookies=True)
                    client.save_cookies(COOKIES_FILE)
                    print("\n  ✅ Cookies guardadas.")
                except Exception as e2:
                    print(f"\n  ❌ Error: {e2}")
                    sys.exit(1)
            else:
                print("  ❌ No se pudo autenticar.")
                sys.exit(1)

    export_cookies()


def export_cookies():
    """Muestra el base64 de las cookies para GitHub Secrets."""
    if not os.path.exists(COOKIES_FILE):
        print("  ❌ No se encontró twitter_cookies.json")
        return

    with open(COOKIES_FILE, "r", encoding="utf-8") as f:
        cookies_json = f.read()

    cookies_b64 = base64.b64encode(cookies_json.encode("utf-8")).decode("utf-8")

    print("\n" + "═" * 60)
    print("  ✅ COOKIES LISTAS PARA GITHUB")
    print("═" * 60)
    print()
    print("  Seguí estos pasos:")
    print()
    print("  1. Andá a tu repositorio en GitHub")
    print("  2. Settings → Secrets and variables → Actions")
    print("  3. Clic en 'New repository secret'")
    print("  4. Name: TWITTER_COOKIES")
    print("  5. Value: pegá TODO el texto de abajo")
    print()
    print("  ┌─ COPIAR DESDE ACÁ ──────────────────────────────┐")
    print()
    print(cookies_b64)
    print()
    print("  └─ HASTA ACÁ ─────────────────────────────────────┘")
    print()

    # También guardar en un archivo por comodidad
    b64_file = "cookies_secret.txt"
    with open(b64_file, "w") as f:
        f.write(cookies_b64)
    print(f"  💾 También guardado en: {b64_file}")
    print(f"     (podés copiar su contenido directamente)")
    print()
    print("  ⚠️  IMPORTANTE: no compartas este texto con nadie.")
    print("     Contiene tu sesión de Twitter/X.")
    print()
    print("  📌 Las cookies expiran periódicamente.")
    print("     Si el Action falla, ejecutá este script de nuevo")
    print("     y actualizá el secret en GitHub.")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

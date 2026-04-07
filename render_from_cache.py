#!/usr/bin/env python3
"""
Renderiza el HTML usando el tweets_data.json ya existente,
sin tocar Twitter ni los tokens/cookies.

Uso:
    python render_from_cache.py
    python render_from_cache.py --data otro.json --out salida.html
"""

import argparse
import json
import os
import sys
import webbrowser

# Forzar UTF-8 en stdout (Windows cp1252 rompe con emojis)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from report_generator import generate_html_report

DEFAULT_DATA = "tweets_data.json"
DEFAULT_OUT = os.path.join("docs", "index.html")


def main():
    parser = argparse.ArgumentParser(description="Render HTML desde cache JSON")
    parser.add_argument("--data", default=DEFAULT_DATA, help=f"JSON de entrada (default: {DEFAULT_DATA})")
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"HTML de salida (default: {DEFAULT_OUT})")
    parser.add_argument("--no-open", action="store_true", help="No abrir el navegador al terminar")
    args = parser.parse_args()

    if not os.path.exists(args.data):
        raise SystemExit(f"❌ No existe el archivo de datos: {args.data}")

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    generate_html_report(data, args.out)

    print(f"✅ HTML generado: {os.path.abspath(args.out)}")

    if not args.no_open:
        try:
            webbrowser.open(f"file://{os.path.abspath(args.out)}")
        except Exception:
            pass


if __name__ == "__main__":
    main()

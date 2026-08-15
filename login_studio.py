"""
Corre este script UNA VEZ por cada canal, en tu PC (no en GitHub Actions),
para guardar la sesion de YouTube Studio ya logueada.

Uso:
    python login_studio.py "NombreDelCanal"

Se abre un navegador de verdad (no headless). Inicia sesion manualmente
con la cuenta de Google de ese canal, navega hasta que veas el dashboard
de YouTube Studio cargado normalmente, y luego vuelve a la terminal y
presiona ENTER. Eso guarda las cookies de sesion en un archivo que el
worker reutiliza despues para tomar capturas sin volver a loguearse.
"""

import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

CREDENTIALS_DIR = Path(__file__).parent / "credentials"


def _session_path(canal_nombre: str) -> Path:
    safe_name = "".join(c if c.isalnum() else "_" for c in canal_nombre)
    return CREDENTIALS_DIR / f"studio_session_{safe_name}.json"


def main(canal_nombre: str):
    CREDENTIALS_DIR.mkdir(exist_ok=True)
    session_path = _session_path(canal_nombre)

    with sync_playwright() as p:
        # Usamos el Chrome real instalado en el sistema (channel="chrome"),
        # no el Chromium interno de Playwright, y ocultamos la marca de
        # automatizacion. Google bloquea el login si detecta un navegador
        # automatizado "normal" (es una proteccion anti-bot de su lado).
        browser = p.chromium.launch(
            headless=False,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        page.goto("https://studio.youtube.com")

        print("\n" + "=" * 60)
        print("Inicia sesion manualmente en el navegador que se abrio,")
        print("con la cuenta de Google dueña del canal:", canal_nombre)
        print("Cuando veas el Dashboard de YouTube Studio cargado,")
        print("vuelve aqui y presiona ENTER.")
        print("=" * 60)
        input("\nPresiona ENTER cuando hayas iniciado sesion... ")

        context.storage_state(path=str(session_path))
        print(f"\nSesion guardada en: {session_path}")

        browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Uso: python login_studio.py "NombreDelCanal"')
        sys.exit(1)
    main(sys.argv[1])
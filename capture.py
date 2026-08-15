"""
Captura de pantalla de YouTube Studio en modo movil, usando la sesion
guardada previamente con login_studio.py.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright

CREDENTIALS_DIR = Path(__file__).parent / "credentials"


def _session_path(canal_nombre: str) -> Path:
    safe_name = "".join(c if c.isalnum() else "_" for c in canal_nombre)
    return CREDENTIALS_DIR / f"studio_session_{safe_name}.json"


def capturar_analytics(canal_nombre: str, canal_youtube_id: str, salida_path: str) -> str:
    """
    Abre YouTube Studio emulando un celular, navega al dashboard de
    Analytics del canal, y guarda un screenshot en salida_path.
    Devuelve la ruta del archivo generado.
    """
    session_path = _session_path(canal_nombre)

    if not session_path.exists():
        raise RuntimeError(
            f"No hay sesion guardada para '{canal_nombre}'. "
            f"Corre primero: python login_studio.py \"{canal_nombre}\""
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Emulacion de un celular (Pixel 7): viewport vertical + user agent movil
        context = browser.new_context(
            storage_state=str(session_path),
            viewport={"width": 412, "height": 915},
            user_agent=(
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
            device_scale_factor=2.6,
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()

        url = f"https://studio.youtube.com/channel/{canal_youtube_id}/analytics/tab-overview/period-default"
        page.goto(url, wait_until="networkidle", timeout=60000)

        # YouTube Studio a veces muestra un interstitial sugiriendo
        # descargar la app nativa cuando detecta un viewport movil.
        # Si aparece, saltamos con el enlace de texto "Ir a Studio".
        try:
            enlace_ir_a_studio = page.get_by_text("IR A STUDIO", exact=False)
            if enlace_ir_a_studio.is_visible(timeout=5000):
                enlace_ir_a_studio.click()
                page.wait_for_timeout(2000)
        except Exception:
            # Si no aparece el interstitial, seguimos normalmente
            pass

        # Espera a que el dashboard cargue de verdad (evita capturar una pantalla vacia/loading)
        page.wait_for_timeout(4000)

        Path(salida_path).parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=salida_path)

        browser.close()

    return salida_path
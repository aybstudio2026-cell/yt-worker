"""
Resuelve la musica que usa cada canal. El campo 'musica_ruta' del canal
puede ser:
  - Una ruta local a un archivo .mp3 ya existente en el worker.
  - Una URL (YouTube, etc.) - en ese caso se descarga el audio con
    yt-dlp y se guarda en cache local, para no volver a descargarlo
    en cada ejecucion.
"""

import hashlib
import subprocess
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "audio_cache"


def _es_url(texto: str) -> bool:
    return texto.startswith("http://") or texto.startswith("https://")


def _ruta_cache_para_url(url: str) -> Path:
    hash_url = hashlib.sha256(url.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{hash_url}.mp3"


def resolver_audio(musica_ruta: str | None) -> str | None:
    """
    Devuelve la ruta local a un archivo de audio usable, o None si no
    hay musica configurada o no se pudo resolver.
    """
    if not musica_ruta:
        return None

    if not _es_url(musica_ruta):
        # Ya es una ruta local
        return musica_ruta if Path(musica_ruta).exists() else None

    CACHE_DIR.mkdir(exist_ok=True)
    destino = _ruta_cache_para_url(musica_ruta)

    if destino.exists():
        # Ya se descargo antes, se reutiliza (ahorra tiempo y ancho de banda)
        return str(destino)

    print(f"     Descargando audio desde: {musica_ruta}")
    comando = [
        "yt-dlp",
        "-x",  # extraer solo audio
        "--audio-format", "mp3",
        "-o", str(destino.with_suffix("")),  # yt-dlp agrega .mp3 solo
        musica_ruta,
    ]
    resultado = subprocess.run(comando, capture_output=True, text=True)

    if resultado.returncode != 0 or not destino.exists():
        print(f"     No se pudo descargar el audio: {resultado.stderr[-500:]}")
        return None

    print(f"     Audio descargado y guardado en cache: {destino}")
    return str(destino)
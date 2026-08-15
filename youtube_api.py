"""
Funciones para interactuar con la YouTube Data API v3.

Maneja:
  - Autenticacion OAuth por canal (guarda/reusa un refresh token).
  - Obtener el numero de vistas actual del canal.
  - Subir un video (short) con titulo, descripcion y tags.
"""

import os
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

CREDENTIALS_DIR = Path(__file__).parent / "credentials"
CLIENT_SECRET_FILE = CREDENTIALS_DIR / "client_secret.json"


def _token_path(canal_nombre: str) -> Path:
    """Cada canal guarda su propio token, ya que cada uno se autoriza
    por separado con una cuenta de Google distinta (o la misma)."""
    safe_name = "".join(c if c.isalnum() else "_" for c in canal_nombre)
    return CREDENTIALS_DIR / f"token_{safe_name}.pickle"


def autorizar_canal(canal_nombre: str) -> Credentials:
    """
    Ejecuta el flujo de autorizacion OAuth por primera vez para un canal.
    Abre el navegador para que apruebes el acceso con la cuenta de Google
    correspondiente a ese canal. Se debe correr UNA sola vez por canal
    (el token queda guardado localmente y se reutiliza despues).
    """
    if not CLIENT_SECRET_FILE.exists():
        raise FileNotFoundError(
            f"No se encontro {CLIENT_SECRET_FILE}. "
            "Descarga el JSON de Google Cloud Console y ponlo ahi "
            "renombrado como 'client_secret.json'."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET_FILE), SCOPES
    )
    credenciales = flow.run_local_server(port=0)

    token_path = _token_path(canal_nombre)
    token_path.parent.mkdir(exist_ok=True)
    with open(token_path, "wb") as f:
        pickle.dump(credenciales, f)

    print(f"Token guardado en {token_path}")
    return credenciales


def obtener_credenciales(canal_nombre: str) -> Credentials:
    """
    Carga el token guardado para el canal. Si esta vencido, lo refresca
    automaticamente. Si no existe ningun token todavia, lanza un error
    indicando que hay que correr autorizar_canal() primero.
    """
    token_path = _token_path(canal_nombre)

    if not token_path.exists():
        raise RuntimeError(
            f"El canal '{canal_nombre}' todavia no fue autorizado. "
            f"Corre: python authorize.py \"{canal_nombre}\""
        )

    with open(token_path, "rb") as f:
        credenciales: Credentials = pickle.load(f)

    if credenciales.expired and credenciales.refresh_token:
        credenciales.refresh(Request())
        with open(token_path, "wb") as f:
            pickle.dump(credenciales, f)

    return credenciales


def obtener_youtube_client(canal_nombre: str):
    credenciales = obtener_credenciales(canal_nombre)
    return build("youtube", "v3", credentials=credenciales)


def obtener_views_canal(canal_nombre: str, canal_youtube_id: str) -> int:
    """Devuelve el total de vistas acumuladas del canal (lifetime)."""
    youtube = obtener_youtube_client(canal_nombre)
    respuesta = (
        youtube.channels()
        .list(part="statistics", id=canal_youtube_id)
        .execute()
    )
    items = respuesta.get("items", [])
    if not items:
        raise RuntimeError(f"No se encontro el canal {canal_youtube_id}")

    return int(items[0]["statistics"]["viewCount"])


def obtener_estadisticas_canal(canal_nombre: str, canal_youtube_id: str) -> dict:
    """Devuelve views y suscriptores actuales del canal en una sola llamada."""
    youtube = obtener_youtube_client(canal_nombre)
    respuesta = (
        youtube.channels()
        .list(part="statistics", id=canal_youtube_id)
        .execute()
    )
    items = respuesta.get("items", [])
    if not items:
        raise RuntimeError(f"No se encontro el canal {canal_youtube_id}")

    stats = items[0]["statistics"]
    return {
        "views": int(stats["viewCount"]),
        "suscriptores": int(stats.get("subscriberCount", 0)),
    }


def subir_video(
    canal_nombre: str,
    archivo_path: str,
    titulo: str,
    descripcion: str,
    tags: list[str],
) -> str:
    """
    Sube un video/short al canal. Devuelve la URL del video publicado.
    """
    youtube = obtener_youtube_client(canal_nombre)

    body = {
        "snippet": {
            "title": titulo,
            "description": descripcion,
            "tags": tags,
            "categoryId": "24",  # Entertainment
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(archivo_path, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    respuesta = None
    while respuesta is None:
        status, respuesta = request.next_chunk()
        if status:
            print(f"  Subiendo... {int(status.progress() * 100)}%")

    video_id = respuesta["id"]
    return f"https://youtube.com/shorts/{video_id}"


def formatear_views(views: int) -> str:
    """Convierte 32900 -> '32.9k' para usar en el texto del overlay."""
    if views >= 1_000_000:
        return f"{views / 1_000_000:.1f}m"
    if views >= 1_000:
        return f"{views / 1_000:.1f}k"
    return str(views)
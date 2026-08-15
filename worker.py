"""
Worker de automatización de canales de YouTube.

Version 1: Solo valida la conexion con Supabase y el flujo de
verificacion de horarios. Todavia NO hace captura de pantalla,
NO genera video y NO sube nada a YouTube - eso se agrega en los
siguientes pasos.

Como funciona:
  - Se ejecuta una vez cada vez que lo corre el Programador de
    tareas de Windows (cada 10 minutos).
  - Revisa que canales activos tienen un horario que coincide con
    la hora/dia actual (con un margen de tolerancia).
  - Si encuentra alguno pendiente para "ahora", crea un registro
    en la tabla `publicaciones` y simula el proceso.
"""

import os
import sys
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from supabase import create_client, Client

from youtube_api import obtener_views_canal, formatear_views

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Zona horaria de referencia para comparar horarios, sin importar si el
# worker corre en tu PC (hora local) o en GitHub Actions (UTC).
ZONA_HORARIA = ZoneInfo("America/Lima")


def ahora() -> datetime:
    return datetime.now(ZONA_HORARIA)

# Margen de tolerancia: si el worker corre cada 10 minutos, un horario
# "coincide" si esta dentro de los ultimos N minutos desde la ultima
# corrida esperada. Esto evita que se salte una publicacion si el
# worker tarda unos segundos de mas en arrancar.
TOLERANCIA_MINUTOS = 10


def conectar_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "Faltan SUPABASE_URL o SUPABASE_KEY en el archivo .env"
        )
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    # Todas las consultas deben ir al schema yt_automation, no al "public"
    return client.schema("yt_automation")


def dia_iso_actual() -> int:
    """Python: lunes=0 ... domingo=6. Nuestro schema usa lunes=1 ... domingo=7."""
    return ahora().isoweekday()


def horario_coincide_ahora(hora_str: str, dias_semana: list[int]) -> bool:
    """
    Determina si un horario (ej. '14:30:00') debe dispararse en este
    momento, dado el margen de tolerancia de TOLERANCIA_MINUTOS.
    """
    momento_actual = ahora()

    if momento_actual.isoweekday() not in dias_semana:
        return False

    hora_horario = datetime.strptime(hora_str, "%H:%M:%S").time()
    objetivo = momento_actual.replace(
        hour=hora_horario.hour,
        minute=hora_horario.minute,
        second=0,
        microsecond=0,
    )

    diferencia = momento_actual - objetivo
    return timedelta(0) <= diferencia <= timedelta(minutes=TOLERANCIA_MINUTOS)


def ya_se_publico_hoy(supabase: Client, horario_id: str) -> bool:
    """Evita publicar dos veces el mismo horario el mismo dia si el
    worker corre varias veces dentro del margen de tolerancia."""
    hoy = ahora().date().isoformat()
    resultado = (
        supabase.table("publicaciones")
        .select("id")
        .eq("horario_id", horario_id)
        .gte("fecha_programada", f"{hoy}T00:00:00")
        .in_("estado", ["procesando", "publicado"])
        .execute()
    )
    return len(resultado.data) > 0


def procesar_horario(supabase: Client, canal: dict, horario: dict):
    print(f"  -> Procesando canal '{canal['nombre']}' (horario {horario['hora']})")

    publicacion = (
        supabase.table("publicaciones")
        .insert(
            {
                "canal_id": canal["id"],
                "horario_id": horario["id"],
                "estado": "procesando",
                "fecha_programada": ahora().isoformat(),
            }
        )
        .execute()
    )
    publicacion_id = publicacion.data[0]["id"]

    try:
        # 1. Obtener views reales del canal vía YouTube Data API
        views = obtener_views_canal(canal["nombre"], canal["canal_youtube_id"])
        views_formateadas = formatear_views(views)
        print(f"     Views actuales: {views} ({views_formateadas})")

        # --- Los siguientes pasos se agregan en los proximos cambios: ---
        # 2. Playwright: captura de pantalla de YouTube Studio (modo movil)
        # 3. FFmpeg/Pillow: generar el video con overlay usando views_formateadas
        # 4. YouTube Data API: subir el video real (subir_video de youtube_api.py)
        #
        # Por ahora solo guardamos las views reales, sin video todavia:
        url_pendiente = "PENDIENTE - falta generar y subir el video"

        supabase.table("publicaciones").update(
            {
                "estado": "publicado",
                "fecha_ejecucion": ahora().isoformat(),
                "views_capturadas": views,
                "url_video_resultante": url_pendiente,
                "log": "Views reales obtenidas OK. Falta captura/video/subida real.",
            }
        ).eq("id", publicacion_id).execute()

        print(f"     Views registradas OK")

    except Exception as e:
        error_texto = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        supabase.table("publicaciones").update(
            {
                "estado": "error",
                "fecha_ejecucion": ahora().isoformat(),
                "log": error_texto,
            }
        ).eq("id", publicacion_id).execute()
        print(f"     ERROR: {e}")


def main():
    print(f"[{ahora()}] Worker iniciado")

    try:
        supabase = conectar_supabase()
    except Exception as e:
        print(f"No se pudo conectar a Supabase: {e}")
        sys.exit(1)

    canales = (
        supabase.table("canales").select("*").eq("activo", True).execute()
    ).data

    if not canales:
        print("No hay canales activos.")
        return

    for canal in canales:
        horarios = (
            supabase.table("horarios")
            .select("*")
            .eq("canal_id", canal["id"])
            .eq("activo", True)
            .execute()
        ).data

        for horario in horarios:
            if not horario_coincide_ahora(horario["hora"], horario["dias_semana"]):
                continue

            if ya_se_publico_hoy(supabase, horario["id"]):
                print(
                    f"  (canal '{canal['nombre']}' ya se publico hoy para "
                    f"este horario, se omite)"
                )
                continue

            procesar_horario(supabase, canal, horario)

    print(f"[{ahora()}] Worker terminado\n")


if __name__ == "__main__":
    main()
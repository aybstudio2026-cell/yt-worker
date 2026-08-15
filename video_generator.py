"""
Generadores de video por formato. Cada funcion recibe los datos ya
obtenidos de la API y produce un archivo .mp4 vertical (1080x1920)
listo para subir como short.

Requiere que 'ffmpeg' este instalado y disponible en el PATH del
sistema (en Windows: https://ffmpeg.org/download.html, agregarlo al
PATH. En GitHub Actions: se instala en el workflow con apt-get).
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS = 30
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  # Linux/GitHub Actions
FONT_BOLD_WINDOWS = "C:/Windows/Fonts/arialbd.ttf"  # fallback para Windows


def _fuente(size: int) -> ImageFont.FreeTypeFont:
    for ruta in (FONT_BOLD, FONT_BOLD_WINDOWS):
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, size)
    return ImageFont.load_default()


def _easing_out(t: float) -> float:
    """Desacelera hacia el final, para que el conteo se sienta natural
    (rapido al inicio, se frena cerca del numero final)."""
    return 1 - (1 - t) ** 3


def _formatear_numero(n: int) -> str:
    return f"{n:,}".replace(",", ",")


def generar_contador_animado(
    views_actuales: int,
    subs_actuales: int,
    audio_path: str | None,
    output_path: str,
    duracion_seg: int = 5,
) -> str:
    """
    Genera un short vertical con dos contadores corriendo en paralelo
    (views y suscriptores) desde 0 hasta el valor actual real.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        total_frames = duracion_seg * FPS

        font_label = _fuente(46)
        font_numero = _fuente(130)
        font_titulo = _fuente(60)

        for i in range(total_frames):
            t = i / (total_frames - 1)
            progreso = _easing_out(min(t * 1.3, 1.0))  # termina de contar un poco antes del final

            views_frame = int(views_actuales * progreso)
            subs_frame = int(subs_actuales * progreso)

            img = Image.new("RGB", (W, H), "#0a0a0a")
            draw = ImageDraw.Draw(img, "RGBA")

            # Fondo con resplandor sutil (simula el brillo morado)
            for r in range(700, 0, -20):
                alpha = int(25 * (1 - r / 700))
                draw.ellipse(
                    [W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r],
                    fill=(147, 51, 234, alpha),
                )

            titulo = "Estadísticas en vivo"
            bbox = draw.textbbox((0, 0), titulo, font=font_titulo)
            draw.text(
                ((W - (bbox[2] - bbox[0])) // 2, 260),
                titulo,
                font=font_titulo,
                fill="#a855f7",
            )

            # Bloque Views
            label_views = "VIEWS"
            bbox = draw.textbbox((0, 0), label_views, font=font_label)
            draw.text(
                ((W - (bbox[2] - bbox[0])) // 2, 650),
                label_views,
                font=font_label,
                fill="#888",
            )
            texto_views = _formatear_numero(views_frame)
            bbox = draw.textbbox((0, 0), texto_views, font=font_numero)
            draw.text(
                ((W - (bbox[2] - bbox[0])) // 2, 720),
                texto_views,
                font=font_numero,
                fill="white",
            )

            # Bloque Suscriptores
            label_subs = "SUSCRIPTORES"
            bbox = draw.textbbox((0, 0), label_subs, font=font_label)
            draw.text(
                ((W - (bbox[2] - bbox[0])) // 2, 1150),
                label_subs,
                font=font_label,
                fill="#888",
            )
            texto_subs = _formatear_numero(subs_frame)
            bbox = draw.textbbox((0, 0), texto_subs, font=font_numero)
            draw.text(
                ((W - (bbox[2] - bbox[0])) // 2, 1220),
                texto_subs,
                font=font_numero,
                fill="#22c55e",
            )

            img.save(tmp_path / f"frame_{i:05d}.png")

        _combinar_frames_a_video(tmp_path, audio_path, output_path, duracion_seg)

    return output_path


def _combinar_frames_a_video(
    frames_dir: Path, audio_path: str | None, output_path: str, duracion_seg: int
):
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg no esta instalado o no esta en el PATH. "
            "Instalalo desde https://ffmpeg.org/download.html "
            "(o 'apt-get install ffmpeg' en Linux/GitHub Actions)."
        )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    comando = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(frames_dir / "frame_%05d.png"),
    ]

    if audio_path and Path(audio_path).exists():
        comando += ["-i", audio_path]

    comando += [
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-t", str(duracion_seg),
    ]

    if audio_path and Path(audio_path).exists():
        comando += ["-c:a", "aac", "-shortest"]

    comando += [output_path]

    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(f"ffmpeg fallo: {resultado.stderr[-2000:]}")
import os
import uuid
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool

# Directorio base de almacenamiento local para documentos subidos
BASE_UPLOAD_DIR = Path("uploads/formularios")


def _ensure_directories(establecimiento_id: int) -> tuple[Path, Path]:
    """Crea las carpetas de fotos y pdfs de forma aislada por establecimiento si no existen."""
    fotos_dir = BASE_UPLOAD_DIR / "fotos" / str(establecimiento_id)
    pdfs_dir = BASE_UPLOAD_DIR / "pdfs" / str(establecimiento_id)
    fotos_dir.mkdir(parents=True, exist_ok=True)
    pdfs_dir.mkdir(parents=True, exist_ok=True)
    return fotos_dir, pdfs_dir


def _convert_image_to_pdf_sync(image_path: Path, pdf_path: Path) -> None:
    """
    Función sincrónica ejecutada en threadpool para no bloquear el event loop.
    Corrige orientación EXIF (común en fotos de celulares) y genera PDF de alta fidelidad.
    """
    with Image.open(image_path) as img:
        # Corregir orientación si la foto viene de smartphone con tag EXIF
        img = ImageOps.exif_transpose(img)
        # Convertir a modo RGB requerido para formato PDF
        if img.mode in ("RGBA", "P"):
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                rgb_img.paste(img, mask=img.split()[3])
            else:
                rgb_img.paste(img)
            rgb_img.save(pdf_path, "PDF", resolution=150.0)
        else:
            rgb_img = img.convert("RGB")
            rgb_img.save(pdf_path, "PDF", resolution=150.0)


class FileStorageService:
    """Servicio de gestión y transformación asíncrona de fotografías a documentos PDF."""

    @staticmethod
    async def save_and_convert_to_pdf(
        file_bytes: bytes,
        filename: str,
        establecimiento_id: int,
        tipo_formulario: str = "estadistica"
    ) -> tuple[str, str]:
        """
        Guarda la imagen subida y genera internamente su correspondiente PDF.
        Retorna las rutas relativas (archivo_foto, archivo_pdf).
        """
        fotos_dir, pdfs_dir = _ensure_directories(establecimiento_id)

        # Generar identificador único y seguro
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_token = uuid.uuid4().hex[:8]
        ext = Path(filename).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".jpg"

        foto_filename = f"{tipo_formulario}_{timestamp}_{unique_token}{ext}"
        pdf_filename = f"{tipo_formulario}_{timestamp}_{unique_token}.pdf"

        foto_path = fotos_dir / foto_filename
        pdf_path = pdfs_dir / pdf_filename

        # Guardar la imagen física en disco
        with open(foto_path, "wb") as f:
            f.write(file_bytes)

        # Convertir a PDF en threadpool para cero cuellos de botella
        await run_in_threadpool(_convert_image_to_pdf_sync, foto_path, pdf_path)

        # Retornar rutas normalizadas con forward slashes
        return str(foto_path).replace("\\", "/"), str(pdf_path).replace("\\", "/")

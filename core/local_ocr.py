"""Bounded local OCR. Tesseract is an explicit external runtime, never downloaded here."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


def options():
    from memory.config_manager import load_api_keys
    cfg = load_api_keys()
    executable = cfg.get('local_ocr_executable','') or shutil.which('tesseract')
    if not executable:
        from core.workspace_store import directory
        import sys
        candidates=[directory()/'ocr'/'tesseract'/'tesseract.exe',Path(sys.executable).parent/'ocr'/'tesseract.exe']
        executable=next((str(path) for path in candidates if path.is_file()),None)
    if not executable:
        for root in (Path('C:/Program Files/Tesseract-OCR'),Path.home()/'scoop/apps/tesseract/current'):
            if (root/'tesseract.exe').is_file():executable=str(root/'tesseract.exe');break
    if not executable or not Path(executable).is_file():
        raise ValueError('OCR uchun Sozlamalarda Tesseract dasturini tanlang.')
    language = cfg.get('local_ocr_languages','uzb+uzb_cyrl+eng+rus')
    import re
    if not isinstance(language,str) or not re.fullmatch(r'[a-z_]+(?:\+[a-z_]+)*',language):
        raise ValueError('OCR tillari noto‘g‘ri.')
    return str(executable), language


def image_text(path,cancelled=None):
    from PIL import Image, ImageOps
    executable,language=options()
    with Image.open(path) as source:
        if source.width*source.height > 25_000_000:
            raise ValueError('OCR rasmi 25 megapikseldan katta.')
        image=ImageOps.exif_transpose(source).convert('RGB')
    with tempfile.TemporaryDirectory(prefix='brave-ocr-') as folder:
        raster=Path(folder)/'page.png';image.save(raster)
        output=Path(folder)/'result'
        # Files avoid stdout pipe deadlocks and keep subprocess output bounded by disk input.
        with (Path(folder)/'error.txt').open('wb') as errors:
            process=subprocess.Popen([executable,str(raster),str(output),'-l',language],
                stdout=subprocess.DEVNULL,stderr=errors,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            deadline=time.monotonic()+45
            try:
                while process.poll() is None:
                    if (cancelled and cancelled.is_set()) or time.monotonic()>deadline:
                        raise ValueError('OCR bekor qilindi yoki vaqt chegarasi tugadi.')
                    time.sleep(.05)
                if process.returncode:
                    raise ValueError('OCR ishlamadi. Tesseract va tanlangan til fayllarini tekshiring.')
            finally:
                if process.poll() is None:process.kill();process.wait()
        with output.with_suffix('.txt').open(encoding='utf-8') as source:
            return source.read(2_000_000)


def pdf_page(path,index,cancelled=None):
    import pypdfium2 as pdfium
    from PIL import Image
    with tempfile.TemporaryDirectory(prefix='brave-pdf-') as folder:
        target=Path(folder)/'page.png'
        document=pdfium.PdfDocument(str(path))
        try:
            page=document[index]
            try:
                width,height=page.get_size()
                scale=min(2.0,(20_000_000/max(1,width*height))**.5)
                bitmap=page.render(scale=scale)
                try:bitmap.to_pil().save(target)
                finally:bitmap.close()
            finally:page.close()
        finally:document.close()
        return image_text(target,cancelled)

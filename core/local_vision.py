"""Bounded image inputs for explicitly requested local multimodal chat."""
import base64
import io
from pathlib import Path

from core.local_documents import IMAGES


def partition(paths, mode='ocr'):
    if mode not in ('ocr', 'vision'):
        raise ValueError('Rasm rejimi noto‘g‘ri.')
    images = [path for path in paths if Path(path).suffix.lower() in IMAGES] if mode == 'vision' else []
    if len(images) > 3:
        raise ValueError('Rasm tahlili uchun ko‘pi bilan 3 ta rasm tanlang.')
    return [path for path in paths if path not in images], images


def encode_images(paths, cancelled):
    from PIL import Image, ImageOps
    if len(paths) > 3:
        raise ValueError('Rasm tahlili uchun ko‘pi bilan 3 ta rasm tanlang.')
    encoded, labels = [], []
    pixels = 0
    for path in paths:
        if cancelled.is_set():
            raise ValueError('Bekor qilindi.')
        with Image.open(path) as source:
            count = source.width * source.height
            pixels += count
            if count > 25_000_000 or pixels > 50_000_000:
                raise ValueError('Rasm juda katta.')
            image = ImageOps.exif_transpose(source).convert('RGB')
            image.thumbnail((2048, 2048))
            with io.BytesIO() as output:
                image.save(output, format='JPEG', quality=90)
                encoded.append(base64.b64encode(output.getvalue()).decode('ascii'))
        labels.append(Path(path).name)
        if cancelled.is_set():
            raise ValueError('Bekor qilindi.')
    return encoded, labels

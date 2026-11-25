"""Replace a chosen text file only after its UTF-8 content is fully written."""
from pathlib import Path
import uuid


def write(path,text):
    target=Path(path);temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(text,encoding='utf-8');temporary.replace(target)
    finally:temporary.unlink(missing_ok=True)

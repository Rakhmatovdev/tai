# Native PyQt6 onedir build. API keys, user data and downloaded models are never collected.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files,copy_metadata
root=Path(SPECPATH).parent
hidden=[p.stem for p in root.glob('brave_*.py')]
hidden += ['actions.'+p.stem for p in (root/'actions').glob('*.py') if p.stem!='__init__']
hidden += ['faster_whisper','pypdfium2','onnxruntime','kaldi_native_fbank','win32com.client','pythoncom','soundfile',
           'googleapiclient.discovery','google_auth_oauthlib','paho.mqtt.client','tinytuya','openpyxl','pdfplumber']
data=[(str(root/'assets'),'assets'),(str(root/'core/prompt.txt'),'core'),
      (str(root/'core/face_model.obj'),'core')]
data += [(str(p),'plugins') for p in (root/'plugins').glob('*.py')]
data += collect_data_files('faster_whisper')
for distribution in ('google-genai','faster-whisper','ctranslate2','huggingface-hub','tokenizers'):
    data += copy_metadata(distribution)
for name in ('dashboard','docs'):
    data.append((str(root/name),name))
a=Analysis([str(root/'brave_desktop.py')],pathex=[str(root)],binaries=[],datas=data,
    hiddenimports=hidden,hookspath=[],hooksconfig={},runtime_hooks=[],
    excludes=['PySide6','PySide2','PyQt5','torch','tensorflow','jax','matplotlib','pytest','IPython','notebook'],noarchive=False)
# Qt on modern Windows uses the OS ICU API. A Conda/Poppler ICU found on PATH
# has version-suffixed exports and breaks QtCore before the window can open.
a.binaries=[entry for entry in a.binaries if Path(entry[0]).name.lower() not in ('icuuc.dll','icudt78.dll')]
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Brave',debug=False,bootloader_ignore_signals=False,
    strip=False,upx=False,console=False,contents_directory='.')
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='Brave')

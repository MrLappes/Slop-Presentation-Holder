# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

block_cipher = None

piper_datas, piper_binaries, piper_hiddenimports = collect_all("piper")

hiddenimports = piper_hiddenimports + [
    "pygame",
    "slop.voices",
    "slop.voices.model_registry",
]

datas = [
    ("templates", "templates"),
    ("morshu-zelda.gif", "."),
    ("Agentic_Shield_Zero_Trust.pdf", "."),
]
datas += piper_datas

a = Analysis(
    ["slop.py"],
    pathex=["."],
    binaries=piper_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SlopPresentationHolder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SlopPresentationHolder",
)

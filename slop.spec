# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None

hiddenimports = collect_submodules("piper")
hiddenimports += collect_submodules("piper_phonemize")
hiddenimports += [
    "pygame",
    "slop.voices",
    "slop.voices.model_registry",
]

datas = [
    ("templates", "templates"),
    ("morshu-zelda.gif", "."),
    ("Agentic_Shield_Zero_Trust.pdf", "."),
]

datas += collect_data_files("piper_phonemize")

# Collect compiled shared libraries (extension modules) from piper_phonemize
piper_phonemize_binaries = collect_dynamic_libs("piper_phonemize")

a = Analysis(
    ["slop.py"],
    pathex=["."],
    binaries=piper_phonemize_binaries,
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

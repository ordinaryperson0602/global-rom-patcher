# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('Tools', 'Tools'), ('assets', 'assets')],
    hiddenimports=['structlog', 'src', 'src.config', 'src.logger', 'src.progress'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'PIL', 'PyQt5', 'wx', '_tkinter', 'tcl', 'tk', 'config', 'core', 'ui'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GRP_v1.0.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # 디버그 심볼 제거로 크기 감소
    upx=False,  # UPX 비활성화로 시작 속도 향상
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
)

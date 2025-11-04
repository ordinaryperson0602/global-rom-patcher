# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 빌드 설정 파일

사용법:
  pyinstaller build.spec
  
생성된 실행 파일:
  dist/롬파일패치도구.exe
"""

import sys
from pathlib import Path

block_cipher = None

# 분석 대상
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('Tools', 'Tools'),
        ('config', 'config'),
        ('core', 'core'),
        ('utils', 'utils'),
        ('steps', 'steps'),
        ('devices', 'devices'),
        ('auto2_optimized.py', '.'),
    ],
    hiddenimports=[
        'config', 'config.paths', 'config.constants', 'config.colors',
        'core', 'core.logger', 'core.progress', 'core.data_manager', 'core.exceptions',
        'utils', 'utils.ui', 'utils.command', 'utils.platform',
        'steps', 'steps.step1_extract', 'steps.step2_analyze', 
        'steps.step3_patch', 'steps.step4_verify',
        'auto2_optimized',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ 아카이브
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# EXE 파일
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='롬파일패치도구',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)


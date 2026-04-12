# -*- coding: utf-8 -*-
"""
简化的PyInstaller打包配置

使用单目录模式，更容易调试和解决问题
"""

block_cipher = None

a = Analysis(
    ['run_ui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ui/styles', 'ui/styles'),
        ('config.yaml', '.'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        'akshare',
        'baostock',
        'pandas',
        'numpy',
        'requests',
        'yaml',
        'tqdm',
        'tenacity',
        'bs4',
        'litellm',
        'json_repair',
        'sqlalchemy',
        'newspaper',
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JusticePlutus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
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
    name='JusticePlutus',
)

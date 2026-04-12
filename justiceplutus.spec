# -*- coding: utf-8 -*-
"""
PyInstaller 打包配置文件

用于将JusticePlutus打包成独立的EXE文件
"""

block_cipher = None

a = Analysis(
    ['run_ui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ui/styles', 'ui/styles'),  # 包含QSS样式表
        ('config.yaml', '.'),  # 包含配置文件
        ('screener', 'screener'),  # 包含screener模块
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
        'litellm',
        'json_repair',
        'sqlalchemy',
        'newspaper3k',
        'lxml',
        'lxml.html',
        'lxml.html.clean',
        'tenacity',
        'bs4',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='JusticePlutus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
)

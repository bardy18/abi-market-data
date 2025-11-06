# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    [r'C:\Users\jason\Documents\Development\ABIMarketData\abi-market-data\trading_app\main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (r'C:\Users\jason\Documents\Development\ABIMarketData\abi-market-data\trading_app\config.yaml', 'trading_app'),
        (r'C:\Users\jason\Documents\Development\ABIMarketData\abi-market-data\mappings\display_mappings.json', 'mappings'),
        (r'C:\Users\jason\Documents\Development\ABIMarketData\abi-market-data\mappings\ocr_mappings.json', 'mappings'),
        (r'C:\Users\jason\Documents\Development\ABIMarketData\abi-market-data\trading_app\icon.ico', 'trading_app'),
    ],
    hiddenimports=[
        'PySide6',
        'matplotlib',
        'pandas',
        'numpy',
        'yaml',
        'boto3',
        'botocore',
        'trading_app.s3_config',
        'trading_app.version',
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
    name='ABI_Trading_Platform',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI application, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'C:\Users\jason\Documents\Development\ABIMarketData\abi-market-data\trading_app\icon.ico',
)

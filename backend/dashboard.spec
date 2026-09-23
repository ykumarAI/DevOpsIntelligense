# PyInstaller spec: builds a single self-contained DevOpsDashboard.exe
# (bundles Python, all dependencies, and the pre-built frontend).
# Build with:  pyinstaller dashboard.spec  (run from the backend/ folder)

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("frontend_dist", "frontend_dist")]
binaries = []
hiddenimports = collect_submodules("uvicorn")

# boto3/botocore ship data files (service models, endpoints) that must be bundled.
for pkg in ("botocore", "boto3"):
    p_datas, p_binaries, p_hidden = collect_all(pkg)
    datas += p_datas
    binaries += p_binaries
    hiddenimports += p_hidden

hiddenimports += ["app.main"]

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DevOpsDashboard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

"""
build.py — Génère FileLab.exe avec PyInstaller
Usage : py build.py
"""

import subprocess
import sys
import shutil
from pathlib import Path

HERE = Path(__file__).parent

def run(cmd):
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(HERE))
    if result.returncode != 0:
        print(f"\nERREUR (code {result.returncode})")
        sys.exit(result.returncode)

# 1. Installer PyInstaller si absent
run([sys.executable, "-m", "pip", "install", "pyinstaller", "--quiet"])

# 2. Nettoyer les builds précédents
for folder in ["build", "dist"]:
    if (HERE / folder).exists():
        shutil.rmtree(HERE / folder)
        print(f"Nettoyé : {folder}/")

# 3. Construire la commande PyInstaller
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--noconsole",                          # Pas de terminal visible
    "--icon", "static/icons/icon.ico",
    "--name", "FileLab",
    # Embarquer les fichiers statiques et les modules compressors
    "--add-data", f"static{';'}static",     # (src;dest) format Windows
    "--add-data", f"compressors{';'}compressors",
    # Imports cachés nécessaires pour FastAPI/uvicorn
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.loops",
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.protocols",
    "--hidden-import", "uvicorn.protocols.http",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "uvicorn.protocols.websockets",
    "--hidden-import", "uvicorn.protocols.websockets.auto",
    "--hidden-import", "uvicorn.lifespan",
    "--hidden-import", "uvicorn.lifespan.on",
    "--hidden-import", "fastapi",
    "--hidden-import", "anyio",
    "--hidden-import", "anyio._backends._asyncio",
    "--hidden-import", "starlette",
    "--hidden-import", "starlette.staticfiles",
    "--hidden-import", "PIL",
    "--hidden-import", "PIL.Image",
    "--hidden-import", "pikepdf",
    "--hidden-import", "zstandard",
    "--hidden-import", "brotli",
    # Point d'entrée
    "main.py",
]

run(cmd)

# 4. Résultat
exe = HERE / "dist" / "FileLab.exe"
if exe.exists():
    size_mb = exe.stat().st_size / (1024 * 1024)
    print(f"\n{'='*50}")
    print(f"  Build réussi !")
    print(f"  Fichier : dist/FileLab.exe")
    print(f"  Taille  : {size_mb:.1f} Mo")
    print(f"{'='*50}\n")
else:
    print("\nERREUR : FileLab.exe introuvable après le build.")
    sys.exit(1)

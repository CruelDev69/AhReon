import PyInstaller.__main__
import os
import shutil

if os.path.exists('build'):
    shutil.rmtree('build')
if os.path.exists('dist'):
    shutil.rmtree('dist')

print("🔨 Building AhReon EXE...")

PyInstaller.__main__.run([
    'main.py',
    '--name=AhReon',
    '--onefile',
    '--windowed',
    '--icon=assets/AhReon.ico',
    '--add-data=assets;assets',
    '--hidden-import=customtkinter',
    '--hidden-import=PIL',
    '--optimize=2',
    '--clean',
    '--noconfirm', 
])

print("✅ Build complete! Check 'dist' folder for AhReon.exe")
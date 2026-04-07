"""PyInstaller packaging script to generate the TheGmStudio Transcriber .exe."""

import PyInstaller.__main__
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PyInstaller.__main__.run([
    os.path.join(BASE_DIR, "main.py"),
    "--name=TheGmstudioTranscriber2",
    "--onedir",
    "--windowed",
    "--noconfirm",
    "--clean",
    # Include customtkinter data (needed to find its assets)
    "--collect-data=customtkinter",
    # Include faster_whisper and ctranslate2
    "--collect-all=faster_whisper",
    "--collect-all=ctranslate2",
    # Application icon
    f"--icon={os.path.join(BASE_DIR, 'thegmstudiologo.ico')}",
    # Add the transcriber package
    f"--add-data={os.path.join(BASE_DIR, 'transcriber')};transcriber",
    # Add logo files to the dist root
    f"--add-data={os.path.join(BASE_DIR, 'thegmstudiologo.png')};.",
    f"--add-data={os.path.join(BASE_DIR, 'thegmstudiologo.ico')};.",
    # Output directory
    f"--distpath={os.path.join(BASE_DIR, 'dist')}",
    f"--workpath={os.path.join(BASE_DIR, 'build')}",
    f"--specpath={os.path.join(BASE_DIR)}",
])

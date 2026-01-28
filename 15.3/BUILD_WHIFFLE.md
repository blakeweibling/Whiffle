# Building the Whiffle folder for Inno Setup (smallest way)

## 1. One-command build

From the project root (15.3):

```powershell
pyinstaller game.spec
```

This produces **dist\Whiffle\** with:
- **Whiffle.exe** (main app)
- Bundled data (assets, configs, data, .env) and Python runtime

## 2. Use the folder with Inno Setup

- Point Inno Setup at **dist\Whiffle** as the "Whiffle" source folder (or copy `dist\Whiffle` to a folder named `Whiffle` next to `WhiffleSetup.iss`).
- Build the installer as usual; it expects `Whiffle\Whiffle.exe` and `Whiffle\assets\`, `Whiffle\data\`, etc.

## 3. Size-reduction choices in `game.spec`

- **Onedir (folder)** – exe + dependencies in a folder instead of one big exe; avoids double compression and keeps size smaller than onefile.
- **strip=True** – strips the exe (smaller binary).
- **upx=True** – compresses the exe and binaries (needs UPX on PATH for full effect).
- **optimize=1** – compiles bytecode with basic optimizations (e.g. no `assert`).
- **excludes** – tkinter, matplotlib, pandas, scipy, sklearn, PIL, pytest, etc. are excluded so they are not bundled unless something imports them.
- **No `high_score_proof` / `requirements.txt` in datas** – installer or app creates `high_score_proof`; `requirements.txt` is not needed at runtime.

## 4. Optional: even smaller

- Install **UPX** and ensure it’s on PATH so `upx=True` is used.
- If PyInstaller puts everything in **dist\Whiffle\_internal**, either:
  - Build with:  
    `pyinstaller game.spec --contents-directory .`  
    so files stay next to `Whiffle.exe` and match what Inno expects, or  
  - Change Inno Setup `Source` paths to use `Whiffle\_internal\...` where needed.
- Keep **ultralytics**/YOLO and **torch** – they are required and large; most of the size comes from them.

## 5. openh264 DLL

- If **openh264-1.8.0-win64.dll** is in the project root when you run `pyinstaller game.spec`, it is added to the bundle automatically.
- Otherwise copy it into **dist\Whiffle** after building (the Inno script installs it from the Whiffle folder).

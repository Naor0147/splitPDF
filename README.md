# PDF Stitcher

<p align="center">
	<strong>Turn PDF pages into clean stitched PNGs in seconds.</strong><br/>
	Desktop-first, fast, and simple.
</p>

<p align="center">
	<img alt="platform" src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0A84FF" />
	<img alt="python" src="https://img.shields.io/badge/Python-3.10%2B-1F6FEB" />
	<img alt="ui" src="https://img.shields.io/badge/UI-CustomTkinter-111827" />
	<img alt="packaging" src="https://img.shields.io/badge/Build-PyInstaller-2563EB" />
</p>

---

## What You Get

| Capability         | Details                                                 |
| ------------------ | ------------------------------------------------------- |
| PDF page stitching | Merge multiple pages into one PNG output                |
| Layout modes       | Vertical or Horizontal composition                      |
| Smart cleanup      | Remove large whitespace blocks with adjustable strength |
| Flexible output    | Default folder or custom destination                    |
| Smooth workflow    | Progress feedback + auto-open output folder             |

## Fast Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Launch the app

```bash
python pdf_stitcher_app.py
```

## Build a Standalone EXE (Windows)

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name PDFStitcher --onefile pdf_stitcher_app.py
```

Build output:

- `dist/PDFStitcher.exe`

Copy that EXE anywhere and run it directly.

## How To Use

1. Click **Choose PDF** and select your file.
2. Pick **Pages per image** (1-20).
3. Choose **Vertical** or **Horizontal** layout.
4. Optional: enable **Remove large empty spaces** and tune strength.
5. Optional: enable **Use custom destination**.
6. Click **Generate Images**.

## Output Location

Default output (when custom destination is off):

- `F:/splitPdf/<pdf_name>/`

This default is the same when running from Python or from the built EXE.

## Project Files

- `pdf_stitcher_app.py` - application source code
- `requirements.txt` - runtime dependencies

## Troubleshooting

If imports are missing:

```bash
pip install --upgrade -r requirements.txt
```

If Windows Defender warns on unsigned EXE files, this is common for local builds. Keep your own build and optionally whitelist your build folder.

## License

Personal/internal use unless you add your own license file.

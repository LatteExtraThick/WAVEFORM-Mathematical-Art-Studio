# WAVEFORM — Mathematical Art Studio

WAVEFORM is a Python desktop application for creating mathematical artwork. It combines freehand drawing with mathematical curve conversion and direct generation of waves and geometric shapes.

![WAVEFORM logo](assets/waveform_logo.png)

## Features

- **Freehand drawing:** draw with the mouse and convert strokes into mathematical representations.
- **Curve conversion:** simplify captured points with the Ramer–Douglas–Peucker algorithm and fit connected cubic Bézier segments.
- **Mathematical waves:** generate sine, cosine, tangent, square, triangle, and sawtooth waves with adjustable parameters.
- **Geometric shapes:** create circles, ellipses, squares, rectangles, triangles, polygons, stars, and spirals.
- **Colour and fill:** customize fill and outline colours for generated shapes.
- **Views:** inspect original, mathematical, and overlay views.
- **Projects:** save and reopen editable `.wproj` projects.
- **Export:** export artwork and mathematical definitions.

## Mathematical representation

Freehand strokes are represented using piecewise cubic Bézier curves:

```
B(t) = (1-t)^3 P0
     + 3(1-t)^2 t P1
     + 3(1-t)t^2 P2
     + t^3 P3,     0 ≤ t ≤ 1
```

Separate freehand strokes remain separate paths. Generated waves and shapes use their corresponding function or parametric definitions.

## Requirements

- Python 3.10 or newer
- NumPy
- Pillow
- Tkinter (usually included with the standard Windows Python installer)

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run from source

Open the project directory in a terminal and run:

```bash
python main.py
```

## Windows desktop build

The repository includes a PyInstaller specification and Windows build script.

1. On Windows 10/11, install Python 3.10 or newer.
2. Run `build_windows.bat`.
3. Launch `dist/WAVEFORM/WAVEFORM.exe`.

To build a standard Setup installer, install [Inno Setup](https://jrsoftware.org/isinfo.php), then run:

```powershell
ISCC.exe installer\WAVEFORM.iss
```

## Download

Visit the [GitHub Releases](https://github.com/LatteExtraThick/WAVEFORM-Mathematical-Art-Studio/releases) page for published Windows installer and portable downloads. Releases are produced by the GitHub Actions workflow in `.github/workflows/release-windows.yml` when a version tag (for example `v1.0.0`) is pushed.

## Tests

Run the algorithm test suite:

```bash
python -m unittest discover -s tests -v
```

## Project structure

```
WAVEFORM/
├── main.py
├── waveform/
│   ├── __init__.py
│   └── art_engine.py
├── assets/
│   ├── waveform_logo.png
│   └── waveform.ico
├── tests/
│   └── test_art_engine.py
├── installer/
│   └── WAVEFORM.iss
├── .github/
│   └── workflows/
│       └── release-windows.yml
├── WAVEFORM.spec
├── build_windows.bat
├── requirements.txt
└── README.md
```

## License

No license has been selected for this repository yet.

# DicomReslice0p2

A small standalone Windows app that loads a DICOM series, resamples it to a
**uniform 0.2 mm isotropic** voxel spacing, and exports the result as a **new
DICOM series**. The heavy lifting is performed by the
[3D Slicer](https://download.slicer.org/) installation on the PC; this app is a
Python-based GUI that drives Slicer automatically.

*Developed by **Team InterOral**.*

> 🇰🇷 한국어 설명서: [README_KR.txt](README_KR.txt) &nbsp;·&nbsp; 🇬🇧 English guide: [README_EN.txt](README_EN.txt)

## Download

Get the latest build from the
[**Releases**](https://github.com/TeamInterOral/DicomReslice0p2/releases/latest)
page — no need to clone the repository:

- `DicomReslice0p2.exe` — the application (single file)
- `DicomReslice0p2_v1.0.zip` — the app bundled with the README files
- `DicomReslice0p2.exe.sha256` — checksum to verify the download (see below)

## Requirements

- Windows PC
- [3D Slicer](https://download.slicer.org/) installed (5.x; developed and
  verified on 5.12.0)

## Usage

1. Run `DicomReslice0p2.exe`.
2. **DICOM folder** — choose the folder containing the source DICOM series.
3. **Slicer.exe** — auto-detected; browse manually if needed.
4. **Spacing (mm)** — default `0.2`.
5. Click **Run**.

The result is written to a `corrected` subfolder inside the selected DICOM
folder. Patient and study identity are preserved; the output is a new series
(`SeriesDescription: corrected 0.2 mm`, `SeriesNumber 9001`). The original DICOM
files are left untouched. A run log (`corrected\reslice_log_<date_time>.txt`) is
saved automatically.

## Verify the download (optional)

```powershell
Get-FileHash .\DicomReslice0p2.exe -Algorithm SHA256
```

Compare the result with the value in `DicomReslice0p2.exe.sha256`.

## Support

Found a problem? Please [open an issue](https://github.com/TeamInterOral/DicomReslice0p2/issues)
and attach the `reslice_log_*.txt` file — it contains everything needed to
diagnose the run.

## Build from source (optional)

```
pip install pyinstaller
pyinstaller --noconsole --onefile --name DicomReslice0p2 --version-file version_info.txt dicom_reslice_app.py
```

The result is `dist/DicomReslice0p2.exe`.

---

© Team InterOral

============================================================
 DicomReslice0p2 — uniform 0.2 mm DICOM reslicer
 Developed by Team InterOral  (v1.0.0)
============================================================

This tool loads a DICOM series, resamples it to a uniform 0.2 mm isotropic
voxel spacing, and exports the result as a new DICOM series. The actual
processing is done by the 3D Slicer installed on the PC; this app is a
Python-based GUI that drives Slicer automatically.

[Requirements]
 - Windows PC
 - 3D Slicer installed (5.x; developed and verified on 5.12.0)
   Download: https://download.slicer.org/

[How to use]
 1. Double-click DicomReslice0p2.exe.
 2. "DICOM folder": choose the folder that contains the source DICOM series (Browse…).
 3. "Slicer.exe": auto-detected. If empty or wrong, browse to it manually.
    (e.g. C:\Users\<user>\AppData\Local\slicer.org\3D Slicer 5.x\Slicer.exe)
 4. "Spacing (mm)": default 0.2. Change if needed.
 5. Click "Run". The log streams progress; a message appears when finished.

[Output]
 - A "corrected" subfolder is created inside the selected DICOM folder, holding
   the new, uniformly resampled 0.2 mm DICOM files (IMG0001.dcm ...).
 - Original patient identity (name / ID / birth date / sex) and study info are
   preserved; the result is a NEW series (SeriesDescription "corrected 0.2 mm",
   SeriesNumber 9001).
 - The original DICOM files are left untouched.
 - A run log is saved automatically to corrected\reslice_log_<date_time>.txt
   (on both success and failure, including error details). If something goes
   wrong, send this file to the developer to help diagnose the issue.

[How it works]
 - The heavy lifting (load -> resample -> DICOM export) is performed by the
   installed 3D Slicer.
 - The app launches Slicer in the background, runs ResampleScalarVolume
   (linear interpolation) at the requested spacing, and exports the result as a
   new DICOM series.
 - Re-running on the same folder is safe: a previously created "corrected"
   result is not mistaken for the source (the original series is auto-selected).

[Notes]
 - Non-DICOM files in the folder are ignored, but a clean series-only folder is
   recommended.
 - Interpolation is linear.
 - If the data is already uniform at 0.2 mm, the result is simply repositioned
   onto the same grid.
 - Processing may take from tens of seconds to a few minutes depending on size.
 - To use on another PC, copy just DicomReslice0p2.exe (3D Slicer must be
   installed there).

[Integrity check - optional]
 - Compare the value in the bundled DicomReslice0p2.exe.sha256 with the hash of
   the exe you received to confirm the file was not tampered with.
   PowerShell:  Get-FileHash .\DicomReslice0p2.exe -Algorithm SHA256

[Build from source - optional]
   pip install pyinstaller
   pyinstaller --noconsole --onefile --name DicomReslice0p2 --version-file version_info.txt dicom_reslice_app.py
   Result: dist\DicomReslice0p2.exe

------------------------------------------------------------
 (c) Team InterOral
------------------------------------------------------------

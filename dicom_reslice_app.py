# -*- coding: utf-8 -*-
"""
DicomReslice0p2 — standalone GUI front-end.  Developed by Team InterOral.

Loads a DICOM series, resamples it to a uniform isotropic spacing (default
0.2 mm) and exports the result as a new DICOM series.  The heavy lifting is
performed by the locally installed 3D Slicer; this app only:
  * lets the user pick the DICOM folder,
  * auto-detects (or lets you browse for) Slicer.exe,
  * runs Slicer headless with an embedded worker script,
  * writes the result to <input_folder>/corrected,
  * saves a run log (incl. errors) next to the output.

Build as a single .exe with PyInstaller:
  pyinstaller --noconsole --onefile --name DicomReslice0p2 \
      --version-file version_info.txt dicom_reslice_app.py
"""
import os
import sys
import glob
import tempfile
import threading
import subprocess
import queue
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "DicomReslice0p2"
DEVELOPER = "Team InterOral"
VERSION = "1.0.0"
APP_TITLE = "DICOM 0.2mm Reslice (3D Slicer) — %s" % DEVELOPER

# Substrings of harmless DCMTK/Slicer scan noise that we drop from the log.
NOISE_SUBSTRINGS = (
    "Wrong VR for encapsulated",
    "premature end of stream",
    "Could not read DICOM file",
    "Could not load ",
    "Unknown Tag & Data",
    "DcmFileFormat: Could not determine",
    "DcmItem: Length of element",
    "I/O suspension or premature",
    "TagCacheDatabase adding table",
    "no main window is available",
    "QSqlQuery::prepare: database not open",
    "SQL failed:",
    "Parameter count mismatch",
    "ModuleType: CommandLineModule",
    "Found CommandLine Module",
    "InsertDicomSeriesInHierarchy",
    "command line:",
)

# ---------------------------------------------------------------------------
# Worker script executed *inside* 3D Slicer's own Python.
# Parameters are passed via environment variables to avoid path-quoting issues.
#   RESLICE_INPUT   : folder containing the source DICOM series
#   RESLICE_OUTPUT  : output folder (created if needed; emptied before writing)
#   RESLICE_SPACING : "sx,sy,sz" in mm (e.g. "0.2,0.2,0.2")
# ---------------------------------------------------------------------------
WORKER_SCRIPT = r'''# -*- coding: utf-8 -*-
import os, sys, glob, shutil, traceback
import slicer
from DICOMLib import DICOMUtils

INPUT_DIR  = os.environ["RESLICE_INPUT"]
OUTPUT_DIR = os.environ["RESLICE_OUTPUT"]
SPACING    = os.environ.get("RESLICE_SPACING", "0.2,0.2,0.2")

def log(m):
    print("[reslice] " + str(m)); sys.stdout.flush()

def db_val(uid, group, elem):
    try:
        return slicer.dicomDatabase.instanceValue(uid, "%04x,%04x" % (group, elem))
    except Exception:
        return ""

rc = 0
try:
    log("Input : %s" % INPUT_DIR)
    log("Output: %s" % OUTPUT_DIR)
    log("Spacing: %s mm" % SPACING)

    # Empty the output folder FIRST so the importer never re-scans a previous
    # 'corrected' result that lives inside the input folder.
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for f in glob.glob(os.path.join(OUTPUT_DIR, "*")):
        try:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f, ignore_errors=True)
        except OSError:
            pass

    # 1) Load DICOM series ---------------------------------------------------
    loadedNodeIDs = []
    with DICOMUtils.TemporaryDICOMDatabase() as db:
        DICOMUtils.importDicom(INPUT_DIR, db)
        for pUID in db.patients():
            loadedNodeIDs.extend(DICOMUtils.loadPatientByUID(pUID))

        # Choose the source series. Exclude any previously-exported 'corrected'
        # series (SeriesNumber 9001 or description contains 'corrected'); among
        # the rest pick the one with the most slices.
        candidates = []
        for nid in loadedNodeIDs:
            n = slicer.mrmlScene.GetNodeByID(nid)
            if not (n and n.IsA("vtkMRMLScalarVolumeNode") and n.GetImageData()):
                continue
            uids = (n.GetAttribute("DICOM.instanceUIDs") or "").split()
            sdesc = db_val(uids[0], 0x0008, 0x103E) if uids else ""
            snum  = db_val(uids[0], 0x0020, 0x0011) if uids else ""
            is_corr = (str(snum).strip() == "9001") or ("corrected" in (sdesc or "").lower())
            dimz = n.GetImageData().GetDimensions()[2]
            candidates.append({"node": n, "corr": is_corr, "z": dimz,
                               "desc": sdesc, "num": snum})
        if not candidates:
            raise RuntimeError("No scalar volume loaded from: %s" % INPUT_DIR)
        originals = [c for c in candidates if not c["corr"]]
        pool = originals if originals else candidates
        pool.sort(key=lambda c: c["z"], reverse=True)
        chosen = pool[0]
        volumeNode = chosen["node"]
        log("series candidates=%d (originals=%d); selected: slices=%d desc=%r num=%r"
            % (len(candidates), len(originals), chosen["z"], chosen["desc"], chosen["num"]))

        # capture original identity tags while the temp DB is still open
        ident = {}
        uids = (volumeNode.GetAttribute("DICOM.instanceUIDs") or "").split()
        if uids:
            u0 = uids[0]
            ident["PatientName"]      = db_val(u0, 0x0010, 0x0010)
            ident["PatientID"]        = db_val(u0, 0x0010, 0x0020)
            ident["PatientBirthDate"] = db_val(u0, 0x0010, 0x0030)
            ident["PatientSex"]       = db_val(u0, 0x0010, 0x0040)
            ident["StudyInstanceUID"] = db_val(u0, 0x0020, 0x000D)
            ident["StudyID"]          = db_val(u0, 0x0020, 0x0010)
            ident["StudyDate"]        = db_val(u0, 0x0008, 0x0020)
            ident["StudyDescription"] = db_val(u0, 0x0008, 0x1030)
            ident["Modality"]         = db_val(u0, 0x0008, 0x0060) or "CT"
        log("source identity: %s" % {k: v for k, v in ident.items() if v})

    sx, sy, sz = volumeNode.GetSpacing()
    dims = volumeNode.GetImageData().GetDimensions()
    log("input spacing : %.4f, %.4f, %.4f" % (sx, sy, sz))
    log("input dims    : %s" % (dims,))

    # 2) Resample to uniform isotropic spacing -------------------------------
    outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "corrected")
    params = {
        "InputVolume": volumeNode.GetID(),
        "OutputVolume": outputVolume.GetID(),
        "outputPixelSpacing": SPACING,
        "interpolationType": "linear",
    }
    log("running ResampleScalarVolume -> %s ..." % SPACING)
    cliNode = slicer.cli.runSync(slicer.modules.resamplescalarvolume, None, params)
    if cliNode.GetStatusString() != "Completed":
        raise RuntimeError("ResampleScalarVolume failed: %s" % cliNode.GetStatusString())
    osp = outputVolume.GetSpacing(); odm = outputVolume.GetImageData().GetDimensions()
    log("output spacing: %.4f, %.4f, %.4f" % osp)
    log("output dims   : %s" % (odm,))

    # 3) Export as a new DICOM series ----------------------------------------
    import DICOMScalarVolumePlugin
    shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
    volShItemID = shNode.GetItemByDataNode(outputVolume)
    subjName = ident.get("PatientName") or "Corrected 0.2mm"
    studyName = ident.get("StudyDescription") or "Corrected 0.2mm Study"
    studyItem = shNode.CreateStudyItem(shNode.GetSceneItemID(), studyName)
    patientItem = shNode.CreateSubjectItem(shNode.GetSceneItemID(), subjName)
    shNode.SetItemParent(studyItem, patientItem)
    shNode.SetItemParent(volShItemID, studyItem)

    exporter = DICOMScalarVolumePlugin.DICOMScalarVolumePluginClass()
    exportables = exporter.examineForExport(volShItemID)
    if not exportables:
        raise RuntimeError("Nothing examinable for DICOM export.")
    srcDesc = ident.get("StudyDescription") or ""
    sp1 = SPACING.split(",")[0]
    for exp in exportables:
        exp.directory = OUTPUT_DIR
        # preserve patient/study identity, mark as a new corrected series
        if ident.get("PatientName"):      exp.setTag("PatientName", ident["PatientName"])
        if ident.get("PatientID"):        exp.setTag("PatientID", ident["PatientID"])
        if ident.get("PatientBirthDate"): exp.setTag("PatientBirthDate", ident["PatientBirthDate"])
        if ident.get("PatientSex"):       exp.setTag("PatientSex", ident["PatientSex"])
        if ident.get("StudyInstanceUID"): exp.setTag("StudyInstanceUID", ident["StudyInstanceUID"])
        if ident.get("StudyID"):          exp.setTag("StudyID", ident["StudyID"])
        if ident.get("StudyDate"):        exp.setTag("StudyDate", ident["StudyDate"])
        if ident.get("StudyDescription"): exp.setTag("StudyDescription", ident["StudyDescription"])
        exp.setTag("Modality", ident.get("Modality", "CT"))
        exp.setTag("SeriesDescription", (srcDesc + " corrected %s mm" % sp1).strip())
        exp.setTag("SeriesNumber", "9001")
    log("exporting DICOM ...")
    errMsg = exporter.export(exportables)
    if errMsg:
        log("export() message: %r" % (errMsg,))

    # 4) Flatten: move *.dcm out of the auto-created ScalarVolume_* subfolder
    for sub in glob.glob(os.path.join(OUTPUT_DIR, "ScalarVolume_*")):
        if os.path.isdir(sub):
            for f in glob.glob(os.path.join(sub, "*")):
                dst = os.path.join(OUTPUT_DIR, os.path.basename(f))
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.move(f, dst)
            try:
                os.rmdir(sub)
            except OSError:
                pass

    files = [p for p in glob.glob(os.path.join(OUTPUT_DIR, "*"))
             if os.path.isfile(p) and p.lower().endswith(".dcm")]
    log("files written: %d" % len(files))
    if len(files) < 1:
        raise RuntimeError("Export produced no files.")
    log("SUCCESS")
except Exception as e:
    rc = 1
    log("ERROR: %s" % e)
    traceback.print_exc()
finally:
    sys.stdout.flush()
    slicer.app.quit()
    sys.exit(rc)
'''


def find_slicer():
    """Best-effort auto-detection of an installed Slicer.exe."""
    pats = []
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        pats += [
            os.path.join(local, "slicer.org", "*", "Slicer.exe"),
            os.path.join(local, "NA-MIC", "*", "Slicer.exe"),
        ]
    for pf in (os.environ.get("ProgramFiles", r"C:\Program Files"),
               os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        if pf:
            pats += [
                os.path.join(pf, "Slicer*", "Slicer.exe"),
                os.path.join(pf, "*", "Slicer.exe"),
            ]
    hits = []
    for p in pats:
        hits += glob.glob(p)
    hits = sorted(set(hits))

    def keyf(h):
        try:
            return os.path.getmtime(h)
        except OSError:
            return 0
    hits.sort(key=keyf, reverse=True)
    return hits[0] if hits else ""


def is_noise(line):
    s = line.strip()
    if s == "" or s == "Error:":  # blank / lone DB-insert artifact
        return True
    return any(sub in line for sub in NOISE_SUBSTRINGS)


def run_conversion(input_dir, slicer_exe, spacing_mm, on_line=None):
    """Run the Slicer worker once. Streams filtered lines to on_line(str) and
    writes a run log next to the output. Returns (returncode, log_path).

    This function has no GUI dependency so it can be tested headlessly."""
    spacing3 = "%s,%s,%s" % (spacing_mm, spacing_mm, spacing_mm)
    outdir = os.path.join(input_dir, "corrected")

    def emit(text):
        if on_line:
            on_line(text)

    # write worker script to a temp file
    tmp = tempfile.NamedTemporaryFile("w", suffix="_reslice_worker.py",
                                      delete=False, encoding="utf-8")
    tmp.write(WORKER_SCRIPT)
    tmp.close()

    env = dict(os.environ)
    env["RESLICE_INPUT"] = input_dir
    env["RESLICE_OUTPUT"] = outdir
    env["RESLICE_SPACING"] = spacing3

    cmd = [slicer_exe, "--no-splash", "--no-main-window", "--python-script", tmp.name]

    started = datetime.now()
    header = [
        "%s v%s — by %s" % (APP_NAME, VERSION, DEVELOPER),
        "started : %s" % started.strftime("%Y-%m-%d %H:%M:%S"),
        "input   : %s" % input_dir,
        "output  : %s" % outdir,
        "slicer  : %s" % slicer_exe,
        "spacing : %s mm" % spacing3,
        "-" * 60,
    ]
    captured = list(header)
    for h in header:
        emit(h + "\n")

    rc = -1
    try:
        flags = 0
        if os.name == "nt":
            flags = 0x08000000  # CREATE_NO_WINDOW
        p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace",
                             bufsize=1, creationflags=flags)
        for line in p.stdout:
            if is_noise(line):
                continue
            captured.append(line.rstrip("\n"))
            emit(line)
        p.wait()
        rc = p.returncode
    except Exception as e:
        captured.append("LAUNCHER ERROR: %s" % e)
        emit("LAUNCHER ERROR: %s\n" % e)
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass

    captured.append("-" * 60)
    captured.append("finished: %s  (exit code %s)"
                    % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rc))

    # write the log file next to the output (fall back to the input folder)
    log_dir = outdir if os.path.isdir(outdir) else input_dir
    log_path = os.path.join(
        log_dir, "reslice_log_%s.txt" % started.strftime("%Y%m%d_%H%M%S"))
    try:
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(captured) + "\n")
    except OSError as e:
        emit("Could not write log file: %s\n" % e)
        log_path = ""
    if log_path:
        emit("\nLog saved: %s\n" % log_path)
    return rc, log_path


class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("760x560")
        self.q = queue.Queue()

        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(root)
        frm.pack(fill="x", **pad)

        ttk.Label(frm, text="DICOM folder:").grid(row=0, column=0, sticky="w")
        self.in_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.in_var, width=72).grid(row=0, column=1, sticky="we")
        ttk.Button(frm, text="Browse…", command=self.pick_input).grid(row=0, column=2, padx=4)

        ttk.Label(frm, text="Slicer.exe:").grid(row=1, column=0, sticky="w")
        self.slicer_var = tk.StringVar(value=find_slicer())
        ttk.Entry(frm, textvariable=self.slicer_var, width=72).grid(row=1, column=1, sticky="we")
        ttk.Button(frm, text="Browse…", command=self.pick_slicer).grid(row=1, column=2, padx=4)

        ttk.Label(frm, text="Spacing (mm):").grid(row=2, column=0, sticky="w")
        self.sp_var = tk.StringVar(value="0.2")
        ttk.Entry(frm, textvariable=self.sp_var, width=10).grid(row=2, column=1, sticky="w")

        ttk.Label(frm, text="Output folder:").grid(row=3, column=0, sticky="w")
        self.out_var = tk.StringVar(value="(select a DICOM folder → <folder>\\corrected)")
        ttk.Label(frm, textvariable=self.out_var, foreground="#555").grid(row=3, column=1, sticky="w")

        frm.columnconfigure(1, weight=1)

        btnfrm = ttk.Frame(root)
        btnfrm.pack(fill="x", **pad)
        self.run_btn = ttk.Button(btnfrm, text="Run", command=self.run)
        self.run_btn.pack(side="left")
        self.status = ttk.Label(btnfrm, text="Idle")
        self.status.pack(side="left", padx=12)

        ttk.Label(root, text="Log:").pack(anchor="w", padx=8)
        self.log = tk.Text(root, height=20, wrap="none")
        self.log.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.in_var.trace_add("write", lambda *_: self.update_out())

        ttk.Label(root, text="Developed by %s   ·   v%s" % (DEVELOPER, VERSION),
                  foreground="#777").pack(anchor="e", padx=10, pady=(0, 8))

        self.root.after(100, self.drain)

    def pick_input(self):
        d = filedialog.askdirectory(title="Select DICOM folder")
        if d:
            self.in_var.set(os.path.normpath(d))

    def pick_slicer(self):
        f = filedialog.askopenfilename(title="Select Slicer.exe",
                                       filetypes=[("Slicer", "Slicer.exe"), ("Executable", "*.exe")])
        if f:
            self.slicer_var.set(os.path.normpath(f))

    def update_out(self):
        d = self.in_var.get().strip()
        self.out_var.set(os.path.join(d, "corrected") if d else "(select a DICOM folder → …\\corrected)")

    def append(self, text):
        self.log.insert("end", text)
        self.log.see("end")

    def run(self):
        inp = self.in_var.get().strip()
        slicer_exe = self.slicer_var.get().strip()
        spacing = self.sp_var.get().strip().replace(" ", "")
        if not inp or not os.path.isdir(inp):
            messagebox.showerror(APP_TITLE, "Please select a valid DICOM folder.")
            return
        if not slicer_exe or not os.path.isfile(slicer_exe):
            messagebox.showerror(APP_TITLE, "The Slicer.exe path is not valid.")
            return
        try:
            v = float(spacing)
            if v <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(APP_TITLE, "Spacing must be a number greater than 0 (e.g. 0.2).")
            return

        self.log.delete("1.0", "end")
        self.run_btn.config(state="disabled")
        self.status.config(text="Running…")
        t = threading.Thread(target=self._worker, args=(inp, slicer_exe, v), daemon=True)
        t.start()

    def _worker(self, inp, slicer_exe, spacing):
        rc, log_path = run_conversion(inp, slicer_exe, spacing,
                                      on_line=lambda s: self.q.put(("log", s)))
        self.q.put(("done", (rc, log_path)))

    def drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.append(payload)
                elif kind == "done":
                    rc, log_path = payload
                    self.run_btn.config(state="normal")
                    outdir = os.path.join(self.in_var.get().strip(), "corrected")
                    if rc == 0:
                        self.status.config(text="Done ✓")
                        messagebox.showinfo(
                            APP_TITLE,
                            "Conversion finished.\n\nOutput: %s\nLog: %s" % (outdir, log_path))
                    else:
                        self.status.config(text="Failed (code %s)" % rc)
                        messagebox.showerror(
                            APP_TITLE,
                            "Conversion failed (code %s).\nSee the log:\n%s" % (rc, log_path))
        except queue.Empty:
            pass
        self.root.after(100, self.drain)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

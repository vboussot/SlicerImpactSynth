# ====== Double progress bar (file + overall) download from Hugging Face ======
import hashlib
import os
import shutil
import time
from pathlib import Path

import requests
import slicer
from qt import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QStandardPaths, Qt, QVBoxLayout


class _TwoProgressDialog(QDialog):
    """QDialog avec 2 barres + volumes téléchargés (MB) + Cancel."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent or slicer.util.mainWindow())
        self.setWindowTitle(title)
        self.setModal(True)

        # --- Widgets ---
        self.labelFile = QLabel("Current file:")
        self.barFile = QProgressBar()
        self.barFile.setRange(0, 100)
        self.barFile.setValue(0)
        self.sizeFile = QLabel("0.0 / 0.0 MB")  # ligne d’info sous la barre

        self.labelAll = QLabel("Total progress:")
        self.barAll = QProgressBar()
        self.barAll.setRange(0, 100)
        self.barAll.setValue(0)
        self.sizeAll = QLabel("0.0 / 0.0 MB")

        self.cancelBtn = QPushButton("Cancel")
        self.cancelled = False
        self.cancelBtn.clicked.connect(self._onCancel)

        # --- Layout ---
        lay = QVBoxLayout(self)
        lay.addWidget(self.labelFile)
        lay.addWidget(self.barFile)
        lay.addWidget(self.sizeFile)
        lay.addSpacing(8)
        lay.addWidget(self.labelAll)
        lay.addWidget(self.barAll)
        lay.addWidget(self.sizeAll)
        lay.addSpacing(12)
        hlay = QHBoxLayout()
        hlay.addStretch(1)
        hlay.addWidget(self.cancelBtn)
        lay.addLayout(hlay)
        self.resize(560, 190)

    def _onCancel(self):
        self.cancelled = True

    # -------- Helpers d’affichage --------
    @staticmethod
    def _fmt_size(bytes_val: int | float | None) -> str:
        """Format Mo avec 1 décimale (ou ‘—’ si inconnu)."""
        if not bytes_val or bytes_val <= 0:
            return "—"
        return f"{bytes_val / (1024*1024):.1f} MB"

    def setFileText(self, text: str):
        self.labelFile.setText(f"Current file: {text}")

    # === API “simple” en pourcentage (compat) ===
    def setFilePercent(self, pct: int | None):
        if pct is None:
            self.barFile.setRange(0, 0)
        else:
            if self.barFile.maximum == 0:
                self.barFile.setRange(0, 100)
            self.barFile.setValue(max(0, min(100, int(pct))))

    def setAllPercent(self, pct: int | None):
        if pct is None:
            self.barAll.setRange(0, 0)
        else:
            if self.barAll.maximum == 0:
                self.barAll.setRange(0, 100)
            self.barAll.setValue(max(0, min(100, int(pct))))

    # === Nouvelle API: progression en octets (recommandée) ===
    def setFileBytes(self, done_bytes: int, total_bytes: int | None):
        """Met à jour la barre + le libellé (MB) pour le fichier courant."""
        # Libellé tailles
        done_txt = self._fmt_size(done_bytes)
        total_txt = self._fmt_size(total_bytes)
        self.sizeFile.setText(f"{done_txt} / {total_txt}")

        # Barre
        if total_bytes and total_bytes > 0:
            if self.barFile.maximum == 0:
                self.barFile.setRange(0, 100)
            pct = int(done_bytes * 100 / total_bytes)
            self.barFile.setValue(max(0, min(100, pct)))
        else:
            # total inconnu -> indéterminé
            self.barFile.setRange(0, 0)

    def setAllBytes(self, done_bytes: int, total_bytes: int | None):
        """Met à jour la barre + le libellé (MB) pour l’ensemble."""
        done_txt = self._fmt_size(done_bytes)
        total_txt = self._fmt_size(total_bytes)
        self.sizeAll.setText(f"{done_txt} / {total_txt}")

        if total_bytes and total_bytes > 0:
            if self.barAll.maximum == 0:
                self.barAll.setRange(0, 100)
            pct = int(done_bytes * 100 / total_bytes)
            self.barAll.setValue(max(0, min(100, pct)))
        else:
            self.barAll.setRange(0, 0)


def is_file_downloaded(local_path: Path, expected_size: int, expected_sha: str) -> bool:
    if not local_path.is_file():
        return False
    if expected_size is not None and expected_size > 0:
        local_size = local_path.stat().st_size
        if abs(local_size - expected_size) > expected_size * 0.01:  # tolérance 1 %
            return False
    sha = hashlib.sha256()
    with open(local_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    if sha.hexdigest() != expected_sha:
        return False
    return True


def download_model(repo_id: str, folder_prefix: str) -> Path:
    base = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)) / "ImpactSynth" / "models"

    api = HfApi()
    info = api.model_info(repo_id=repo_id, files_metadata=True)

    entries = [s for s in info.siblings if s.rfilename.startswith(folder_prefix + "/")]
    if not entries:
        raise FileNotFoundError(f"Aucun fichier sous '{folder_prefix}' dans {repo_id}")

    sizes = {s.rfilename: int(getattr(s, "size", 0) or 0) for s in entries}
    if all(is_file_downloaded(base / entry.rfilename, sizes[entry.rfilename], entry.lfs.sha256) for entry in entries):
        return base / folder_prefix

    total_bytes = sum(sizes.values())

    dlg = _TwoProgressDialog(f"Téléchargement : {repo_id}/{folder_prefix}")
    dlg.setAllPercent(0)
    dlg.setFilePercent(0)
    dlg.show()
    slicer.app.processEvents()

    headers = {"Accept-Encoding": "identity"}
    (base / folder_prefix).mkdir(parents=True, exist_ok=True)

    bytes_done_all = 0
    try:
        for s in entries:
            dest = base / s.rfilename
            if is_file_downloaded(dest, sizes[s.rfilename], s.lfs.sha256):
                bytes_done_all += sizes[s.rfilename]
                dlg.setAllPercent(int(bytes_done_all * 100 / total_bytes))
                slicer.app.processEvents()
                continue

            file_size = sizes[s.rfilename]
            dlg.setFileText(s.rfilename)
            dlg.setFilePercent(0)
            slicer.app.processEvents()

            url = hf_hub_url(repo_id=repo_id, filename=s.rfilename)
            with requests.get(url, headers=headers, stream=True, timeout=120) as r:
                r.raise_for_status()
                file_done = 0
                with open(dest, "wb") as out:
                    for chunk in r.iter_content(8192):
                        if dlg.cancelled:
                            (base / s.rfilename).unlink(missing_ok=True)
                            return None
                        if not chunk:
                            continue
                        out.write(chunk)
                        file_done += len(chunk)
                        bytes_done_all += len(chunk)

                        dlg.setFilePercent(int(file_done * 100 / file_size))
                        dlg.setAllPercent(int(bytes_done_all * 100 / total_bytes))
                        dlg.setFileBytes(file_done, file_size)
                        dlg.setAllBytes(bytes_done_all, total_bytes)
                        slicer.app.processEvents()
            # petite respiration UI
            time.sleep(0.01)

        dlg.setAllPercent(100)
        dlg.setFilePercent(100)
        slicer.app.processEvents()
    finally:
        dlg.close()

    return base / folder_prefix


def get_default_models_dir(default_models_base_dir: Path, default_hf_repositories: list[str]) -> list[str]:
    api = HfApi()
    default_models_dir = []
    for default_hf_repository in default_hf_repositories:
        tree = api.list_repo_tree(repo_id=default_hf_repository)
        default_models_dir += sorted(
            [
                f"{str(default_models_base_dir / entry.path)}:{default_hf_repository}"
                for entry in tree
                if entry.path not in ["README.md", ".gitattributes"]
            ]
        )
    return default_models_dir


def download_total_segmentator_model() -> Path:
    base = (
        Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
        / "ImpactSynth"
        / "segmentation"
        / "TotalSegmentator"
    )
    repo_id = "https://huggingface.co/VBoussot/TotalSegmentator-KonfAI"

    api = HfApi()
    info = api.model_info(repo_id=repo_id, files_metadata=True)
    files = ["M291.pt", "M292.pt", "M293.pt", "M294.pt", "M295.pt", "Model.py", "Prediction_CT.yml"]
    nb_class = [25, 27, 19, 24, 27]

    entries = [s for s in info.siblings if s.rfilename in files]
    print(entries)

    sizes = {s.rfilename: int(getattr(s, "size", 0) or 0) for s in entries}
    if all(is_file_downloaded(base / entry.rfilename, sizes[entry.rfilename], entry.lfs.sha256) for entry in entries):
        return base
    exit(0)
    total_bytes = sum(sizes.values())

    dlg = _TwoProgressDialog(f"Téléchargement : {repo_id}/{folder_prefix}")
    dlg.setAllPercent(0)
    dlg.setFilePercent(0)
    dlg.show()
    slicer.app.processEvents()

    headers = {"Accept-Encoding": "identity"}
    (base / folder_prefix).mkdir(parents=True, exist_ok=True)

    bytes_done_all = 0
    try:
        for s in entries:
            dest = base / s.rfilename
            if is_file_downloaded(dest, sizes[s.rfilename], s.lfs.sha256):
                bytes_done_all += sizes[s.rfilename]
                dlg.setAllPercent(int(bytes_done_all * 100 / total_bytes))
                slicer.app.processEvents()
                continue

            file_size = sizes[s.rfilename]
            dlg.setFileText(s.rfilename)
            dlg.setFilePercent(0)
            slicer.app.processEvents()

            url = hf_hub_url(repo_id=repo_id, filename=s.rfilename)
            with requests.get(url, headers=headers, stream=True, timeout=120) as r:
                r.raise_for_status()
                file_done = 0
                with open(dest, "wb") as out:
                    for chunk in r.iter_content(8192):
                        if dlg.cancelled:
                            (base / s.rfilename).unlink(missing_ok=True)
                            return None
                        if not chunk:
                            continue
                        out.write(chunk)
                        file_done += len(chunk)
                        bytes_done_all += len(chunk)

                        dlg.setFilePercent(int(file_done * 100 / file_size))
                        dlg.setAllPercent(int(bytes_done_all * 100 / total_bytes))
                        dlg.setFileBytes(file_done, file_size)
                        dlg.setAllBytes(bytes_done_all, total_bytes)
                        slicer.app.processEvents()
            # petite respiration UI
            time.sleep(0.01)

        dlg.setAllPercent(100)
        dlg.setFilePercent(100)
        slicer.app.processEvents()
    finally:
        dlg.close()

    return base / folder_prefix

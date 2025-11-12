import importlib.metadata
import itertools
import json
import os
import re
import shutil
import threading
from functools import partial
from pathlib import Path

import numpy as np
import psutil
import SimpleITK as sitk
import slicer
import vtk
from konfai.utils.utils import Model_HF, RepositoryHFError, get_available_models_on_hf_repo
from lib.Logic import Logic
from qt import (
    QCursor,
    QDesktopServices,
    QEventLoop,
    QFile,
    QIcon,
    QMenu,
    QSettings,
    QSize,
    QStandardPaths,
    QTimer,
    QUiLoader,
    QUrl,
    QWidget,
)
from slicer import vtkMRMLLabelMapVolumeNode, vtkMRMLScalarVolumeNode, vtkMRMLTransformNode
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.parameterNodeWrapper import parameterNodeWrapper
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin


def download_models_async(download_function):
    """
    Lance le téléchargement en tâche de fond, sans bloquer la GUI,
    mais bloque le code appelant jusqu'à la fin du téléchargement.
    Retourne (models_path, inference_file_path, model_path).
    """

    dlg = slicer.util.createProgressDialog(
        maximum=0,
        windowTitle="Downloading models",
        labelText="Downloading from Hugging Face...",
        parent=slicer.util.mainWindow(),
    )

    result = {"ok": None, "err": None}

    def worker():
        try:
            result["ok"] = download_function()
        except Exception as e:
            result["err"] = str(e)

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    # Boucle d’attente fluide (GUI réactive)
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(100)

    def check_done():
        if th.is_alive():
            slicer.app.processEvents()
            return
        timer.stop()
        dlg.close()
        loop.quit()

    timer.timeout.connect(check_done)
    timer.start()
    loop.exec_()  # bloque le code appelant mais pas la GUI

    if result["err"]:
        slicer.util.errorDisplay(f"❌ Hugging Face download error:\n{result['err']}")
        raise RuntimeError(result["err"])

    slicer.util.infoDisplay("✅ Downloads completed")
    return result["ok"]


IMPACT_SYNTH_KONFAI_REPO = "VBoussot/ImpactSynth"


class SynthesisTab(Logic):

    def __init__(self, ui_tab, log_callback, progress_callback):
        super().__init__(log_callback, progress_callback)

        ui_tab.setMRMLScene(slicer.mrmlScene)
        self.ui = slicer.util.childWidgetVariables(ui_tab)

        self.description_expanded = False
        model_names = get_available_models_on_hf_repo(IMPACT_SYNTH_KONFAI_REPO)

        for model_name in model_names:
            try:
                model = Model_HF(IMPACT_SYNTH_KONFAI_REPO + ":" + model_name)
            except RepositoryHFError as e:
                slicer.util.errorDisplay(str(e), detailedText=getattr(e, "details", None) or "")
                return
            self.ui.modelComboBox.addItem(model.get_display_name(), model)

        self.ui.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.update_parameter_node_from_GUI)
        self.ui.modelComboBox.currentTextChanged.connect(self.update_parameter_node_from_GUI)
        self.ui.outputSCTSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.update_parameter_node_from_GUI)

        self.ui.addModelButton.clicked.connect(self.on_add_model)
        self.ui.removeModelButton.clicked.connect(self.on_remove_model)
        self.ui.modelComboBox.currentIndexChanged.connect(self.on_model_selected)

        iconPath = os.path.join(os.path.dirname(__file__), "Resources", "Icons", "gear.png")
        self.ui.configButton.setIcon(QIcon(iconPath))
        self.ui.configButton.setIconSize(QSize(18, 18))
        self.ui.configButton.clicked.connect(self.on_open_config)

        self.ui.toggleDescriptionButton.clicked.connect(self.on_toggle_description)
        self.on_model_selected(0)

    def on_open_tab(self):
        pass

    def updateGUIFromParameterNode(self, caller=None, event=None):
        pass

    def initialize_parameter_node(self):
        """
        Ensure parameter node exists and observed.
        """
        # Select default input nodes if nothing is selected yet to save a few clicks for the user
        if not self._parameterNode.GetNodeReference("InputVolume"):
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
            if firstVolumeNode:
                self._parameterNode.SetNodeReferenceID("InputVolume", firstVolumeNode.GetID())
        if not self._parameterNode.GetParameter("Model"):
            self._parameterNode.SetParameter("Model", self.ui.modelComboBox.itemData(0))

    def update_parameter_node_from_GUI(self, caller=None, event=None):
        """
        This method is called when the user makes any change in the GUI.
        The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
        """

        if self._parameterNode is None:
            return

        wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

        self._parameterNode.SetNodeReferenceID("Synthesis/InputVolume", self.ui.inputVolumeSelector.currentNodeID)
        self._parameterNode.SetParameter("Synthesis/Model", str(self.ui.modelComboBox.currentIndex))
        self._parameterNode.SetNodeReferenceID("Synthesis/OutputSCT", self.ui.outputSCTSelector.currentNodeID)

        if self._parameterNode.GetNodeReference("Synthesis/InputVolume"):
            self._parameterNode.SetParameter("is_run", "True")
            self._parameterNode.SetParameter("run_tooltip", "Start synthesis")
        else:
            self._parameterNode.SetParameter("is_run", "False")
            self._parameterNode.SetParameter("run_tooltip", "Select input volume")

        self._parameterNode.EndModify(wasModified)

    def _save_models_dir_list_in_settings(self) -> None:
        settings = QSettings()
        # settings.setValue(SETTING_MODEL_DIR_KEY, json.dumps(list(self.models.keys())))

    def on_model_selected(self, index):
        """Handle model selection and display its description."""
        model: Model_HF = self.ui.modelComboBox.itemData(index)
        self.ui.removeModelButton.setEnabled(False)
        self.description_expanded = False
        self.on_toggle_description()

        self.ui.ensembleSpinBox.setMaximum(model.get_number_of_models())
        self.ui.ensembleSpinBox.setValue(model.get_number_of_models())
        self.ui.ttaSpinBox.setEnabled(model.get_maximum_tta() > 0)
        self.ui.ttaSpinBox.setMaximum(model.get_maximum_tta())

        self.ui.mcDropoutSpinBox.setEnabled(model._mc_dropout > 0)
        self.ui.mcDropoutSpinBox.setMaximum(model._mc_dropout)

    def on_toggle_description(self):
        model = self.ui.modelComboBox.currentData

        if self.description_expanded:
            self.ui.modelDescriptionLabel.setText(model.get_description())
            self.ui.toggleDescriptionButton.setText("Less ▲")
        else:
            self.ui.modelDescriptionLabel.setText(model.get_short_description())
            self.ui.toggleDescriptionButton.setText("More ▼")
        self.description_expanded = not self.description_expanded

    def on_remove_model(self):
        cb = self.ui.modelComboBox
        idx = cb.currentIndex
        model_dir = self.ui.modelComboBox.currentData

        mb = QMessageBox()
        mb.setIcon(QMessageBox.Warning)
        mb.setWindowTitle("Remove model?")
        mb.setText(f"Do you really want to remove “{model_dir}” from the list?")
        mb.setInformativeText("This will remove the model entry from the extension’s list.")
        mb.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        mb.setDefaultButton(QMessageBox.Cancel)

        chk = QCheckBox("Also delete the folder from disk")
        chk.setChecked(False)
        mb.setCheckBox(chk)

        if mb.exec_() != QMessageBox.Yes:
            return

        cb.removeItem(idx)

        if chk.isChecked() and model_dir and os.path.isdir(model_dir):
            try:
                # Basic safety: never allow deleting critical folders
                dangerous = {os.path.expanduser("~"), "/", "C:\\"}
                if os.path.abspath(model_dir) in dangerous:
                    raise RuntimeError(f"Refusing to delete a critical directory: {model_dir}")

                shutil.rmtree(model_dir)
                QMessageBox.information(
                    None, "Folder deleted", f"The folder has been successfully deleted:\n{model_dir}"
                )
            except Exception as e:
                QMessageBox.critical(None, "Deletion error", f"Failed to delete folder:\n{model_dir}\n\n{e}")

    def on_open_config(self):
        """
        Open configuration file when user clicks "Open config" button.
        """
        model: Model_HF = self.ui.modelComboBox.currentData
        _, inference_file_path, _ = model.download(0)
        QDesktopServices.openUrl(QUrl.fromLocalFile(Path(inference_file_path).parent))

    def on_add_model(self):
        m = QMenu()
        act_folder = m.addAction("Add from folder…")
        act_hf = m.addAction("Add from Hugging Face…")
        act_ft = m.addAction("Setup fine-tuning")
        chosen = m.exec_(QCursor.pos())
        if chosen is None:
            return
        """if chosen is act_folder:
            self.on_add_folder()
        elif chosen is act_hf:
            self.on_add_hf()
        elif chosen is act_ft:
            self.on_add_ft()"""

    def on_add_folder(self):
        model_dir = QFileDialog.getExistingDirectory(None, "Select Model Folder", os.path.expanduser("~"))
        if not model_dir:
            return
        if model_dir + ":None" in self.models:
            QMessageBox.information(None, "Info", f"This name {model_dir} is already in the list.")
        try:
            model = Model(Path(model_dir), None)
        except ModelConfigError as e:
            slicer.util.errorDisplay(str(e), detailedText=getattr(e, "details", None) or "")
            return

        for model_tmp in self.models.values():
            if model_tmp.get_display_name() == model.get_display_name():
                QMessageBox.warning(
                    None,
                    "Duplicate Model Name",
                    f"A model named “{model_tmp.get_display_name()}” already exists in the list.\n\n"
                    "Each model must have a unique display name.",
                )
                return
        self.models[model_dir + ":None"] = model
        self.ui.modelComboBox.addItem(model.get_display_name(), model_dir + ":None")
        self.ui.modelComboBox.setCurrentIndex(self.ui.modelComboBox.findData(model_dir + ":None"))
        slicer.app.processEvents()

    def on_add_hf(self):
        text = QInputDialog.getText(
            None, "Add from Hugging Face", "Enter repo id (e.g. org/model or org/model@rev):", QLineEdit.Normal
        )
        if not text.strip():
            return
        repo_id = text.strip()
        # (Optionnel) Valider l’existence via huggingface_hub si dispo
        try:
            from huggingface_hub import HfApi

            api = HfApi()
            try:
                api.model_info(repo_id.split("@")[0])  # essaie comme modèle
            except Exception:
                api.dataset_info(repo_id.split("@")[0])  # sinon dataset
        except Exception:
            pass  # pas bloquant

        out_dir = QFileDialog.getExistingDirectory(slicer.util.mainWindow(), "Choisir le dossier de destination")
        if not out_dir:
            return

    def on_add_ft(self):
        # Choisir le dossier parent
        parent_dir = QFileDialog.getExistingDirectory(self.parent, "Choose parent directory for the new model")
        if not parent_dir:
            return

        # Nom du nouveau modèle
        name, ok = QInputDialog.getText(self.parent, "Fine tune", "New model name (folder will be created):")
        if not ok or not name.strip():
            return
        # Slug safe
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip())
        if not safe:
            QMessageBox.warning(self.parent, "Invalid name", "Please enter a valid name.")
            return

        # Créer le dossier (ajoute suffixe _1, _2 si existe)
        base = Path(parent_dir)
        target = base / safe
        if target.exists():
            i = 1
            while (base / f"{safe}_{i}").exists():
                i += 1
            target = base / f"{safe}_{i}"
        try:
            target.mkdir(parents=True, exist_ok=False)
            (target / "README.txt").write_text("Fine-tune model folder (empty).\n")
        except Exception as e:
            QMessageBox.critical(self.parent, "Create folder failed", str(e))
            return

        # Ajoute dans la combo
        self.ui.modelComboBox.addItem(f"{target.name} (ft)", str(target))
        self.ui.modelComboBox.setCurrentIndex(self.ui.modelComboBox.count() - 1)
        if hasattr(self.logic, "logCallback") and self.logic.logCallback:
            self.logic.logCallback(f"Fine-tune folder created: {target}")

    def update_GUI_from_parameter_node(self, caller=None, event=None):
        """
        This method is called whenever parameter node is changed.
        The module GUI is updated to show the current state of the parameter node.
        """
        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return

        # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
        self._updatingGUIFromParameterNode = True

        # Update node selectors and sliders
        self.ui.inputVolumeSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputVolume"))
        model = self._parameterNode.GetParameter("Model")
        self.ui.modelComboBox.setCurrentIndex(self.ui.modelComboBox.findData(model))
        self.ui.outputSCTSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputSCT"))

        # Update buttons states and tooltips
        inputVolume = self._parameterNode.GetNodeReference("InputVolume")
        if inputVolume:
            self.ui.runButton.toolTip = _("Start synthesis")
            self.ui.runButton.enabled = True
        else:
            self.ui.runButton.toolTip = _("Select input volume")
            self.ui.runButton.enabled = False

        referenceVolume = self._parameterNode.GetNodeReference("InputVolume")
        outputSCTVolume = self._parameterNode.GetNodeReference("OutputSCT")
        transform = self._parameterNode.GetNodeReference("ImpactTransform")
        if referenceVolume and referenceVolume.GetImageData() and outputSCTVolume and outputSCTVolume.GetImageData():
            if not transform:
                newTransform = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "IdentityTransform")
                self.ui.impactTransformSelector.setCurrentNode(newTransform)
                self._parameterNode.SetNodeReferenceID("ImpactTransform", self.ui.impactTransformSelector.currentNodeID)
            self.ui.updateMetricButton.enabled = True
        else:
            self.ui.updateMetricButton.enabled = False

        if inputVolume:
            self.ui.outputSCTSelector.baseName = _("{volume_name} sCT").format(volume_name=inputVolume.GetName())
            self.ui.outputSegmentationSelector.baseName = _("{volume_name} seg").format(
                volume_name=inputVolume.GetName()
            )

        # All the GUI updates are done
        self._updatingGUIFromParameterNode = False

    def get_sCT(self) -> sitk.Image:
        mha_files = list((self.workdir / "Predictions").rglob("*.mha"))
        result = None
        for file in mha_files:
            name = file.name
            is_var = name.endswith("var.mha")
            is_numbered = re.search(r"_\d+\.mha$", name) is not None
            if not is_var and not is_numbered:
                result = sitk.ReadImage(str(file))
        return result

    def get_sCT_var(self) -> sitk.Image:
        mha_files = list((self.workdir / "Predictions").rglob("*.mha"))
        result = None
        for file in mha_files:
            name = file.name
            is_var = name.endswith("var.mha")
            if is_var:
                result = sitk.ReadImage(str(file))
        return result

    def get_sCT_list(self) -> list[sitk.Image]:
        mha_files = list((self.workdir / "Predictions").rglob("*.mha"))
        results = []
        for file in mha_files:
            name = file.name
            is_var = name.endswith("var.mha")
            is_numbered = re.search(r"_\d+\.mha$", name) is not None
            if is_numbered:
                results.append(sitk.ReadImage(str(file)))
        return results

    def process(self, device: str) -> None:
        model: Model_HF = self.ui.modelComboBox.currentData
        self.workdir = Path(slicer.util.tempDirectory())
        self._parameterNode.SetParameter("Synthesis/workdir", str(self.workdir))
        cmd = [
            "konfai",
            "PREDICTION_HF",
            "-y",
            "--MODEL",
            str(self.ui.ensembleSpinBox.value),
            "--tta",
            str(self.ui.ttaSpinBox.value),
            "--config",
            f"{model.repo_id}:{model.model_name}",
        ]
        if device != "cpu":
            cmd += ["--gpu", device]
        else:
            cmd += ["--cpu", "1"]

        dataset_p = self.workdir / "Dataset" / "P001"
        dataset_p.mkdir(parents=True, exist_ok=True)

        volumeStorageNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLVolumeArchetypeStorageNode")
        volumeStorageNode.SetFileName(str(dataset_p / "Volume.nii.gz"))
        volumeStorageNode.UseCompressionOff()
        volumeStorageNode.WriteData(self.ui.inputVolumeSelector.currentNode())
        volumeStorageNode.UnRegister(None)

        self.proc = slicer.util.launchConsoleProcess(cmd, useStartupEnvironment=False, cwd=str(self.workdir))
        self.wait()

        arr = sitk.GetArrayFromImage(self.get_sCT())

        if not self.ui.outputSCTSelector.currentNode():
            self.ui.outputSCTSelector.addNode()

        slicer.util.updateVolumeFromArray(self.ui.outputSCTSelector.currentNode(), arr)
        self.ui.outputSCTSelector.currentNode().CopyOrientation(self.ui.inputVolumeSelector.currentNode())

        slicer.util.setSliceViewerLayers(
            foreground=self.ui.outputSCTSelector.currentNode(),
            background=self.ui.inputVolumeSelector.currentNode(),
            fit=True,
            foregroundOpacity=0.5,
        )


TOTAL_SEGMENTATOR_KONFAI_REPO = "VBoussot/TotalSegmentator-KonfAI"
MR_SEGMENTATOR_KONFAI_REPO = "VBoussot/MRSegmentator-KonfAI"


class SegmentationTab(Logic):

    def __init__(self, ui_tab, log_callback, progress_callback):
        super().__init__(log_callback, progress_callback)

        ui_tab.setMRMLScene(slicer.mrmlScene)
        self.ui = slicer.util.childWidgetVariables(ui_tab)

        self.ui.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.update_parameter_node_from_GUI)
        self.ui.outputSegmentationSelector.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.update_parameter_node_from_GUI
        )
        self.ui.foldsSpinBox.connect("valueChanged(int)", self.update_parameter_node_from_GUI)

        for model_name in get_available_models_on_hf_repo(MR_SEGMENTATOR_KONFAI_REPO):
            model_HF = Model_HF(f"{MR_SEGMENTATOR_KONFAI_REPO}:{model_name}")
            self.ui.modelComboBox.addItem(model_HF.get_display_name(), model_HF)

        for model_name in get_available_models_on_hf_repo(TOTAL_SEGMENTATOR_KONFAI_REPO):
            model_HF = Model_HF(f"{TOTAL_SEGMENTATOR_KONFAI_REPO}:{model_name}")
            self.ui.modelComboBox.addItem(model_HF.get_display_name(), model_HF)

        iconPath = os.path.join(os.path.dirname(__file__), "Resources", "Icons", "gear.png")
        self.ui.configButton.setIcon(QIcon(iconPath))
        self.ui.configButton.setIconSize(QSize(18, 18))
        self.ui.configButton.clicked.connect(self.on_open_config)
        self.ui.modelComboBox.currentIndexChanged.connect(self.on_model_selected)

        self.ui.addModelButton.clicked.connect(self.on_add_model)
        self.on_model_selected(0)

    def on_start(self):
        self.update_parameter_node_from_GUI()

    def on_add_model(self):
        m = QMenu()
        act_folder = m.addAction("Add from folder…")
        act_hf = m.addAction("Add from Hugging Face…")
        act_ft = m.addAction("Setup fine-tuning")
        chosen = m.exec_(QCursor.pos())
        if chosen is None:
            return
        """if chosen is act_folder:
            self.on_add_folder()
        elif chosen is act_hf:
            self.on_add_hf()
        elif chosen is act_ft:
            self.on_add_ft()"""

    def on_model_selected(self, index):
        state = self.ui.modelComboBox.currentData.repo_id == MR_SEGMENTATOR_KONFAI_REPO
        self.ui.removeModelButton.setEnabled(False)
        self.ui.label_mode.setEnabled(state)
        self.ui.foldsSpinBox.setEnabled(state)

    def on_open_config(self):
        """o
        Open configuration file when user clicks "Open config" button.
        """
        model: Model_HF = self.ui.modelComboBox.currentData
        _, inference_file_path, _ = model.download(0)
        QDesktopServices.openUrl(QUrl.fromLocalFile(Path(inference_file_path).parent))

    def update_parameter_node_from_GUI(self, caller=None, event=None):
        """
        This method is called when the user makes any change in the GUI.
        The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
        """
        if self._parameterNode is None:
            return

        wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

        self._parameterNode.SetNodeReferenceID("Segmentation/InputVolume", self.ui.inputVolumeSelector.currentNodeID)
        self._parameterNode.SetNodeReferenceID(
            "Segmentation/OutputSegmentation", self.ui.outputSegmentationSelector.currentNodeID
        )
        self._parameterNode.SetParameter("Segmentation/number_of_fold", str(self.ui.foldsSpinBox.value))
        if self._parameterNode.GetNodeReference("Segmentation/InputVolume"):
            self._parameterNode.SetParameter("is_run", "True")
            self._parameterNode.SetParameter("run_tooltip", "Start segmentation")
        else:
            self._parameterNode.SetParameter("is_run", "False")
            self._parameterNode.SetParameter("run_tooltip", "Select input volume")

        self._parameterNode.EndModify(wasModified)

    def updateGUIFromParameterNode(self, caller=None, event=None):
        pass

    def get_segmentation(self):
        mha_files = list((self.workdir / "Predictions").rglob("*.mha"))
        return sitk.ReadImage(str(mha_files[0]))

    def process(self, device: str) -> None:
        model = self.ui.modelComboBox.currentData
        self.workdir = Path(slicer.util.tempDirectory())
        cmd = [
            "konfai",
            "PREDICTION_HF",
            "-y",
            "--config",
            f"{model.repo_id}:{model.model_name}",
        ]
        if self.ui.modelComboBox.currentData.repo_id == MR_SEGMENTATOR_KONFAI_REPO:
            cmd += ["--MODEL", str(self.ui.foldsSpinBox.value)]
        if device != "cpu":
            cmd += ["--gpu", device]
        else:
            cmd += ["--cpu", "1"]

        dataset_p = self.workdir / "Dataset" / "P001"
        dataset_p.mkdir(parents=True, exist_ok=True)

        volumeStorageNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLVolumeArchetypeStorageNode")
        volumeStorageNode.SetFileName(str(dataset_p / "Volume.nii.gz"))
        volumeStorageNode.UseCompressionOff()
        volumeStorageNode.WriteData(self.ui.inputVolumeSelector.currentNode())
        volumeStorageNode.UnRegister(None)

        self.proc = slicer.util.launchConsoleProcess(cmd, useStartupEnvironment=False, cwd=self.workdir)
        self.wait()

        img = self.get_segmentation()
        arr = sitk.GetArrayFromImage(img)

        if not self.ui.outputSegmentationSelector.currentNode():
            self.ui.outputSegmentationSelector.addNode()

        slicer.util.updateVolumeFromArray(self.ui.outputSegmentationSelector.currentNode(), arr)
        self.ui.outputSegmentationSelector.currentNode().CopyOrientation(self.ui.inputVolumeSelector.currentNode())

        slicer.util.setSliceViewerLayers(
            label=self.ui.outputSegmentationSelector.currentNode(),
            background=self.ui.inputVolumeSelector.currentNode(),
            fit=True,
        )


class QualityTab(Logic):

    def __init__(self, ui_tab, log_callback, progress_callback):
        super().__init__(log_callback, progress_callback)

        ui_tab.setMRMLScene(slicer.mrmlScene)
        self.ui = slicer.util.childWidgetVariables(ui_tab)

        self.ui.sCTVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.update_parameter_node_from_GUI)
        self.ui.referenceVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.update_parameter_node_from_GUI)
        self.ui.referenceMaskSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.update_parameter_node_from_GUI)
        self.ui.impactTransformSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.update_parameter_node_from_GUI)

        self.ui.showErrorMapButton.clicked.connect(self.on_error_map)
        self.ui.exportUncertaintyButton.clicked.connect(self.on_export_uncertainty)

    def updateGUIFromParameterNode(self, caller=None, event=None):
        pass

    def on_open_tab(self):
        self.update_parameter_node_from_GUI()

    def update_parameter_node_from_GUI(self, caller=None, event=None):
        """
        This method is called when the user makes any change in the GUI.
        The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
        """

        if self._parameterNode is None:
            return

        wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

        self._parameterNode.SetNodeReferenceID("ReferenceVolume", self.ui.referenceVolumeSelector.currentNodeID)
        self._parameterNode.SetNodeReferenceID("ReferenceMask", self.ui.referenceMaskSelector.currentNodeID)
        self.synthesis_workdir = Path(self._parameterNode.GetParameter("Synthesis/workdir"))

        mha_files = list((self.synthesis_workdir / "Predictions").rglob("*.mha"))
        for file in mha_files:
            name = file.name
            is_numbered = re.search(r"_\d+\.mha$", name) is not None
            if is_numbered:
                self.ui.showErrorMapButton.setEnabled(True)
                self.ui.exportUncertaintyButton.setEnabled(True)
                break

        self._parameterNode.EndModify(wasModified)

    def on_error_map(self):
        if not self.ui.uncertaintyOutputSelector.currentNode():
            self.ui.uncertaintyOutputSelector.addNode()
        image = self.get_sCT_var()

        arr = sitk.GetArrayFromImage(image)

        slicer.util.updateVolumeFromArray(self.ui.uncertaintyOutputSelector.currentNode(), arr)

        spacing = image.GetSpacing()
        origin = image.GetOrigin()
        direction = image.GetDirection()

        mat = vtk.vtkMatrix4x4()
        for i in range(3):
            for j in range(3):
                mat.SetElement(i, j, direction[i * 3 + j])
            mat.SetElement(i, 3, origin[i])
        self.ui.uncertaintyOutputSelector.currentNode().SetIJKToRASMatrix(mat)
        self.ui.uncertaintyOutputSelector.currentNode().SetSpacing(spacing)

        slicer.util.setSliceViewerLayers(background=self.ui.uncertaintyOutputSelector.currentNode(), fit=True)

    def on_export_uncertainty(self):
        for i, image in enumerate(self.get_sCT_list()):
            self.add_volume_to_export(image, i, exportFolderName="Export")

    def ensure_export_folder(self, name="Export"):
        sh = slicer.mrmlScene.GetSubjectHierarchyNode()
        sceneItemID = sh.GetSceneItemID()

        children = vtk.vtkIdList()
        sh.GetItemChildren(sceneItemID, children)
        for i in range(children.GetNumberOfIds()):
            itemID = children.GetId(i)
            if sh.GetItemLevel(itemID) == "Folder" and sh.GetItemName(itemID) == name:
                return itemID

        return sh.CreateFolderItem(sceneItemID, name)

    def add_volume_to_export(self, image, i, exportFolderName="Export"):
        import numpy as np
        import vtk

        arr = sitk.GetArrayFromImage(image)
        arr = np.asarray(arr)

        # arr : numpy [k, y, x] (Z,Y,X). Si ton array est [z,y,x] c’est bon pour Slicer.
        node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", f"sCT_{i}")
        slicer.util.updateVolumeFromArray(node, arr)  # d'abord les voxels

        # --- métadonnées venant d'ITK/SimpleITK (LPS) ---
        spacing_lps = image.GetSpacing()  # (sx, sy, sz)
        origin_lps = np.array(image.GetOrigin(), dtype=float)  # (ox, oy, oz)
        dir_lps = np.array(image.GetDirection(), dtype=float).reshape(3, 3)

        # --- conversion LPS -> RAS ---
        L2R = np.diag([-1.0, -1.0, 1.0])
        dir_ras = L2R @ dir_lps
        origin_ras = L2R @ origin_lps

        # --- construire IJK->RAS = [dir_ras * spacing | origin_ras] ---
        m = vtk.vtkMatrix4x4()
        m.Identity()
        for r in range(3):
            for c in range(3):
                m.SetElement(r, c, float(dir_ras[r, c]))
            m.SetElement(r, 3, float(origin_ras[r]))

        node.SetIJKToRASMatrix(m)  # ⬅️ c'est CETTE méthode qu'il faut appeler
        print(m)
        node.SetSpacing(spacing_lps)
        node.Modified()

        sh = slicer.mrmlScene.GetSubjectHierarchyNode()
        exportFolderID = self.ensure_export_folder(exportFolderName)
        itemID = sh.GetItemByDataNode(node)
        sh.SetItemParent(itemID, exportFolderID)

        return node

    def get_image_metrics(
        self,
        sCTVolume: vtkMRMLScalarVolumeNode,
        referenceVolume: vtkMRMLScalarVolumeNode,
        maskVolume: vtkMRMLScalarVolumeNode,
        transform: vtkMRMLTransformNode,
    ) -> tuple[float, float, float]:
        import torch
        from konfai.metric.measure import MAE, PSNR, SSIM

        mae = MAE()
        psnr = PSNR()
        ssim = SSIM()
        outputNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", sCTVolume.GetName() + "_toRef")

        params = {
            "inputVolume": sCTVolume.GetID(),
            "referenceVolume": referenceVolume.GetID(),  # grille cible
            "outputVolume": outputNode.GetID(),
            "interpolationType": "linear",  # "NearestNeighbor" | "Linear" | "BSpline"
            "warpTransform": transform.GetID(),
        }

        slicer.cli.runSync(slicer.modules.resamplescalarvectordwivolume, None, params)

        sCT_data = torch.tensor(slicer.util.arrayFromVolume(outputNode)).to(torch.float32)
        reference_data = torch.tensor(slicer.util.arrayFromVolume(referenceVolume)).to(torch.float32)
        references = [reference_data]
        if maskVolume and maskVolume.GetImageData():
            references += [torch.tensor(slicer.util.arrayFromVolume(maskVolume)).to(torch.uint8)]

        return mae(sCT_data, *references)[1], psnr(sCT_data, *references)[1], ssim(sCT_data, *references)[1]

    def run_segmentation(self, volume: vtkMRMLScalarVolumeNode, segmentationVolume: vtkMRMLLabelMapVolumeNode, device):
        cmd = [
            "konfai",
            "PREDICTION_HF",
            "-y",
            "--config",
            "VBoussot/MRSegmentator-KonfAI:MRSegmentator",
            "--MODEL",
            "1",
        ]
        if device != "cpu":
            cmd += ["--gpu", device]
        else:
            cmd += ["--cpu", "1"]

        dataset_p = self.workdir / "Dataset" / "P001"
        dataset_p.mkdir(parents=True, exist_ok=True)

        volumeStorageNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLVolumeArchetypeStorageNode")
        volumeStorageNode.SetFileName(str(dataset_p / "Volume.nii.gz"))
        volumeStorageNode.UseCompressionOff()
        volumeStorageNode.WriteData(volume)
        volumeStorageNode.UnRegister(None)

        self.proc = slicer.util.launchConsoleProcess(cmd, useStartupEnvironment=False, cwd=self.workdir)
        self.wait()

        mha_files = list((self.workdir / "Predictions").rglob("*.mha"))
        arr = sitk.GetArrayFromImage(sitk.ReadImage(str(mha_files[0])))

        slicer.util.updateVolumeFromArray(segmentationVolume, arr)
        segmentationVolume.CopyOrientation(volume)

    def dice_score(self, y_true: np.ndarray, y_pred: np.ndarray, label: int = None):
        intersection = np.sum(y_true * y_pred)
        denom = np.sum(y_true) + np.sum(y_pred)

        if denom == 0:
            return 1.0 if np.sum(y_true) == np.sum(y_pred) else 0.0

        return float(2.0 * intersection / denom)

    def get_segmentation_metrics(
        self,
        sct_volume: vtkMRMLScalarVolumeNode,
        sct_segmentation_volume: vtkMRMLLabelMapVolumeNode,
        reference_volume: vtkMRMLScalarVolumeNode,
        reference_segmentation_volume: vtkMRMLLabelMapVolumeNode,
        transform: vtkMRMLTransformNode,
        device,
    ) -> tuple[float, float]:
        self.run_segmentation(sct_volume, sct_segmentation_volume, device)
        self.run_segmentation(reference_volume, reference_segmentation_volume, device)

        params = {
            "inputVolume": sct_segmentation_volume.GetID(),
            "referenceVolume": reference_segmentation_volume.GetID(),  # grille cible
            "outputVolume": sct_segmentation_volume.GetID(),
            "interpolationType": "nn",
            "warpTransform": transform.GetID(),
        }

        slicer.cli.runSync(slicer.modules.resamplescalarvectordwivolume, None, params)

        sCT_segmentation_data = slicer.util.arrayFromVolume(sct_segmentation_volume)
        reference_segmentation_data = slicer.util.arrayFromVolume(reference_segmentation_volume)
        return self.dice_score(sCT_segmentation_data, reference_segmentation_data), 2.1

    def get_sCT_var(self) -> sitk.Image:
        mha_files = list((self.synthesis_workdir / "Predictions").rglob("*.mha"))
        result = None
        for file in mha_files:
            name = file.name
            is_var = name.endswith("var.mha")
            if is_var:
                result = sitk.ReadImage(str(file))
        return result

    def get_sCT_list(self) -> list[sitk.Image]:
        mha_files = list((self.synthesis_workdir / "Predictions").rglob("*.mha"))
        results = []
        for file in mha_files:
            name = file.name
            is_numbered = re.search(r"_\d+\.mha$", name) is not None
            if is_numbered:
                results.append(sitk.ReadImage(str(file)))
        return results

    def process(self, device):
        if not self.ui.impactTransformSelector.currentNodeID:
            newTransform = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "IdentityTransform")
            self.ui.impactTransformSelector.setCurrentNode(newTransform)

        self.workdir = Path(slicer.util.tempDirectory())

        mae, psnr, ssim = self.get_image_metrics(
            self.ui.sCTVolumeSelector.currentNode(),
            self.ui.referenceVolumeSelector.currentNode(),
            self.ui.referenceMaskSelector.currentNode(),
            self.ui.impactTransformSelector.currentNode(),
        )

        sct_segmentation_volume = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLLabelMapVolumeNode", self.ui.sCTVolumeSelector.currentNode().GetName() + "seg_toRef"
        )
        reference_segmentation_volume = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLLabelMapVolumeNode", self.ui.referenceVolumeSelector.currentNode().GetName() + "seg"
        )

        dice, hd95 = self.get_segmentation_metrics(
            self.ui.sCTVolumeSelector.currentNode(),
            sct_segmentation_volume,
            self.ui.referenceVolumeSelector.currentNode(),
            reference_segmentation_volume,
            self.ui.impactTransformSelector.currentNode(),
            device,
        )
        print(dice)
        self.ui.maeValue.placeholderText = f"{mae:.3f}"
        self.ui.psnrValue.placeholderText = f"{psnr:.3f}"
        self.ui.ssimValue.placeholderText = f"{ssim:.3f}"

        self.ui.diceValue.placeholderText = f"{dice:.3f}"
        self.ui.hd95Value.placeholderText = f"{hd95:.3f}"


#
# ImpactSynth
#


class ImpactSynth(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("Impact Synth")
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Synthesis")]
        self.parent.dependencies = []
        self.parent.contributors = [
            "Valentin Boussot (University of Rennes, France)",
            "Cédric Hémon (University of Rennes, France)",
            "Jean-Louis Dillenseger (University of Rennes, France)",
        ]
        self.parent.helpText = _(
            """
ImpactSynth is a 3D Slicer extension for whole-body synthetic CT (sCT) generation from MR or CBCT images, 
built upon the <a href="https://github.com/vboussot/KonfAI">KonfAI</a> framework.  
It provides a reproducible and configurable interface for deep learning–based image synthesis, 
leveraging pretrained models and modular pipelines defined in YAML configurations.  

For more information, please visit the <a href="https://github.com/vboussot/SlicerImpactSynth">official documentation</a>.
"""
        )
        self.parent.acknowledgementText = _(
            """
This module was originally developed by Valentin Boussot (University of Rennes, France).
It integrates the KonfAI deep learning framework for medical image synthesis.

If you use ImpactSynth in your research, please cite the following work:  
Boussot V., Dillenseger J.-L.:  
<b>KonfAI: A Modular and Fully Configurable Framework for Deep Learning in Medical Imaging.</b>  
<a href="https://arxiv.org/abs/2508.09823">https://arxiv.org/abs/2508.09823</a>
"""
        )


#
# ImpactSynthWidget
#


def load_ui_to(container: QWidget, path: str) -> QWidget:
    layout = container.layout()

    # charge le .ui (peut être un chemin fichier ou une ressource :/…)
    loader = QUiLoader(container)
    f = QFile(path)
    if not f.open(QFile.ReadOnly):
        raise RuntimeError(f"Impossible d'ouvrir le .ui: {path}")
    try:
        w = loader.load(f, container)
    finally:
        f.close()

    layout.addWidget(w)
    return w


class ImpactSynthWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.running = False
        self._parameterNode = None
        self.moduleName = "ImpactSynth"

    def createParameterNode(self):
        """
        Create a new parameter node
        The node is of vtkMRMLScriptedModuleNode class. Module name is added as an attribute to allow filtering
        in node selector widgets (attribute name: ModuleName, attribute value: the module's name).
        This method can be overridden in derived classes to create a default parameter node with all
        parameter values set to their default.
        """
        if slicer.mrmlScene is None:
            return

        node = slicer.mrmlScene.CreateNodeByClass("vtkMRMLScriptedModuleNode")
        node.UnRegister(None)  # object is owned by the Python variable now
        node.SetSingletonTag(self.moduleName)
        # Add module name in an attribute to allow filtering in node selector widgets
        # Note that SetModuleName is not used anymore as it would be redundant with the ModuleName attribute.
        node.SetAttribute("ModuleName", self.moduleName)
        node.SetName(slicer.mrmlScene.GenerateUniqueName(self.moduleName))
        return node

    def setup(self) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        ui_widget = slicer.util.loadUI(self.resourcePath("UI/ImpactSynth.ui"))
        self.layout.addWidget(ui_widget)
        self.ui = slicer.util.childWidgetVariables(ui_widget)
        # parameterNode = slicer.mrmlScene.AddNode(self.createParameterNode())

        self.tabs = {}
        self.currentTab = None
        self.tabs["synthesisTab"] = SynthesisTab(
            load_ui_to(self.ui.synthesisTab, self.resourcePath("UI/SynthesisTab.ui")), self.add_log, self.progress
        )
        self.tabs["segmentationTab"] = SegmentationTab(
            load_ui_to(self.ui.segmentationTab, self.resourcePath("UI/SegmentationTab.ui")), self.add_log, self.progress
        )
        # self.tabs["registrationTab"] = RegistrationTab(load_ui_to(self.ui.registrationTab, self.resourcePath("UI/RegistrationTab.ui")), self.add_log, self.progress)
        self.tabs["qualityTab"] = QualityTab(
            load_ui_to(self.ui.qualityTab, self.resourcePath("UI/QualityTab.ui")), self.add_log, self.progress
        )

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        ui_widget.setMRMLScene(slicer.mrmlScene)

        available_devices = self._get_available_devices()
        for available_device in available_devices:
            self.ui.deviceComboBox.addItem(available_device[0], available_device[1])
        self.ui.deviceComboBox.currentIndexChanged.connect(self.on_device_changed)
        self.ui.deviceComboBox.setCurrentIndex(0 if len(available_devices) == 0 else 1)

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.on_scene_start_close)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.on_scene_end_close)
        self.ui.mainTabWidget.currentChanged.connect(self.on_tab_changed)

        iconPath = os.path.join(os.path.dirname(__file__), "Resources", "Icons", "folder.png")
        self.ui.openTempButton.setIcon(QIcon(iconPath))
        self.ui.openTempButton.setIconSize(QSize(18, 18))
        self.ui.openTempButton.clicked.connect(self.on_open_workdir)
        self.ui.openTempButton.setEnabled(False)

        self.ui.runButton.clicked.connect(self.on_run_button)

        # Make sure parameter node is initialized (needed for module reload)

        self.update_ram()
        self.update_VRAM()
        self.on_tab_changed()
        self.ui.runButton.setEnabled(True)
        self.initializeParameterNode()

    def _get_available_devices(self) -> list[tuple[str, str | None]]:
        available_devices = [("cpu [slow]", None)]
        try:
            from torch.cuda import device_count, get_device_name, is_available
        except:
            slicer.util.pip_install("konfai")

        if is_available():
            combos = []
            nb_gpu = device_count()
            for r in range(1, nb_gpu + 1):
                combos.extend(itertools.combinations(range(nb_gpu), r))
            for device in combos:
                device_name = get_device_name(device[0])
                index = str(device[0])
                for i in device[1:]:
                    deviceName += f",{get_device_name(i)}"
                    index += f"-{i}"
                available_devices.append((f"gpu {index} - {device_name}", index))
        return available_devices

    def on_tab_changed(self):
        self.tabs[self.ui.mainTabWidget.currentWidget().name].on_open_tab()

    def cleanup(self):
        """
        Called when the application closes and the module widget is destroyed.
        """
        self.removeObservers()

    def enter(self):
        """
        Called each time the user opens this module.
        """
        # Make sure parameter node exists and observed
        self.initializeParameterNode()

    def exit(self):
        """
        Called each time the user opens a different module.
        """
        pass

    def on_scene_start_close(self, caller, event):
        """
        Called just before the scene is closed.
        """
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def on_scene_end_close(self, caller, event):
        """
        Called just after the scene is closed.
        """
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self):
        """
        Ensure parameter node exists and observed.
        """
        self.setParameterNode(self.getParameterNode())

    def setParameterNode(self, inputParameterNode):
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """
        # Unobserve previously selected parameter node and add an observer to the newly selected.
        # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
        # those are reflected immediately in the GUI.

        if self._parameterNode is not None:
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

        self._parameterNode = inputParameterNode

        if self._parameterNode is not None:
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

        for tab in self.tabs.values():
            tab._parameterNode = self._parameterNode

        # Initial GUI update
        self.updateGUIFromParameterNode()

    def updateGUIFromParameterNode(self, caller=None, event=None):
        """
        This method is called whenever parameter node is changed.
        The module GUI is updated to show the current state of the parameter node.
        """

        if self._parameterNode is None:
            return

        # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
        self._updatingGUIFromParameterNode = True
        for tab in self.tabs.values():
            tab.updateGUIFromParameterNode(caller, event)

        # Update buttons states and tooltips
        self.ui.runButton.enabled = self._parameterNode.GetParameter("is_run") == "True"
        self.ui.runButton.toolTip = _(self._parameterNode.GetParameter("run_tooltip"))

    def getParameterNode(self):
        """
        Return the first available parameter node for this module
        If no parameter nodes are available for this module then a new one is created.
        """
        parameterNode = slicer.mrmlScene.GetSingletonNode(self.moduleName, "vtkMRMLScriptedModuleNode")
        if parameterNode:
            # After close scene, ModuleName attribute may be removed, restore it now
            if parameterNode.GetAttribute("ModuleName") != self.moduleName:
                parameterNode.SetAttribute("ModuleName", self.moduleName)
            return parameterNode
        # no parameter node was found for this module, therefore we add a new one now
        parameterNode = slicer.mrmlScene.AddNode(self.createParameterNode())
        return parameterNode

    def update_ram(self):
        """Update RAM usage display"""
        ram = psutil.virtual_memory()
        used_GB = (ram.total - ram.available) / (1024**3)
        total_GB = ram.total / (1024**3)
        self.ui.ramLabel.text = _("RAM used: {used:.1f} GB / {total:.1f} GB").format(used=used_GB, total=total_GB)
        self.ui.ramProgressBar.value = used_GB / total_GB * 100
        slicer.app.processEvents()  # force update

    def on_device_changed(self):
        self.update_ram()
        self.update_VRAM()

    def update_VRAM(self):
        """Update VRAM usage display"""
        device = self.ui.deviceComboBox.currentData
        if device is not None:
            try:
                import pynvml

                used_GB = 0
                total_GB = 0
                pynvml.nvmlInit()
                for index in device.split(","):
                    info = pynvml.nvmlDeviceGetMemoryInfo(pynvml.nvmlDeviceGetHandleByIndex(int(index)))
                    used_GB += info.used / (1024**3)
                    total_GB += info.total / (1024**3)
                self.ui.gpuLabel.show()
                self.ui.gpuProgressBar.show()
                self.ui.gpuLabel.text = _("VRAM used: {used:.1f} GB / {total:.1f} GB").format(
                    used=used_GB, total=total_GB
                )
                self.ui.gpuProgressBar.value = used_GB / total_GB * 100
            except Exception as e:
                self.ui.gpuLabel.text = _("VRAM used: n/a")
        else:
            self.ui.gpuLabel.hide()
            self.ui.gpuProgressBar.hide()
        slicer.app.processEvents()  # force update

    def add_log(self, text: str) -> None:
        """Append text to log window"""
        self.update_ram()
        self.update_VRAM()
        self.ui.logText.appendPlainText(text)
        slicer.app.processEvents()  # force update

    def progress(self, value: int, speed: float) -> None:
        """Update progress bar"""
        self.ui.progressBar.value = value
        self.ui.speedLabel.text = _("{speed}").format(speed=speed)
        slicer.app.processEvents()  # force update

    def on_open_workdir(self):
        """
        Open synthesis workdir when user clicks "Open workdir" button.
        """
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.currentTab.get_workdir()))

    def on_run_button(self):
        """
        Run processing when user clicks "Apply" button.
        """
        if not self.running:
            self.currentTab = self.tabs[self.ui.mainTabWidget.currentWidget().name]
            self.progress(0, "0 it/s")
            self.running = True
            self.ui.logText.plainText = ""
            self.ui.runButton.text = "Stop"
            slicer.app.processEvents()
            self.ui.openTempButton.setEnabled(True)
            self.currentTab.remove_work_dir()
            try:
                self.currentTab.process(self.ui.deviceComboBox.currentData)
                self.ui.logText.appendPlainText("\n" + _("Processing finished."))
                self.running = False
            except Exception() as e:
                print(e)
                self.on_run_button()

        else:
            self.ui.runButton.enabled = False
            self.ui.openTempButton.setEnabled(False)
            slicer.app.processEvents()
            self.currentTab.stop()
            slicer.app.processEvents()
            import time

            time.sleep(3)
            self.ui.runButton.enabled = True
            self.running = False
        self.ui.runButton.text = "Run"
        self.update_ram()
        self.update_VRAM()

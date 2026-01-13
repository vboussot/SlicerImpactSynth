# Copyright (c) 2025 Valentin Boussot
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

from KonfAI import KonfAIAppTemplateWidget, KonfAICoreWidget, _is_reload_setup
from qt import QWidget
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import ScriptedLoadableModule, ScriptedLoadableModuleWidget


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
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Image Synthesis")]
        self.parent.dependencies = ["KonfAI"]
        self.parent.contributors = [
            "Valentin Boussot (University of Rennes, France)",
            "Cédric Hémon (University of Rennes, France)",
            "Jean-Louis Dillenseger (University of Rennes, France)",
        ]
        self.parent.helpText = _(
            "<p>"
            "ImpactSynth is a 3D Slicer extension for whole-body synthetic CT (sCT) generation "
            "from MR or CBCT images, built upon the "
            '<a href="https://github.com/vboussot/KonfAI">KonfAI</a> framework.<br>'
            "It provides a reproducible and configurable interface for deep learning-based "
            "image synthesis, leveraging pretrained models and modular pipelines defined "
            "in YAML configurations."
            "</p>"
            "<p>"
            "For more information, please visit the "
            '<a href="https://github.com/vboussot/SlicerImpactSynth">official documentation</a>.'
            "</p>"
        )

        self.parent.acknowledgementText = _(
            "<p>"
            "This module was originally developed by Valentin Boussot "
            "(University of Rennes, France).<br>"
            "It integrates the KonfAI deep learning framework for medical image synthesis."
            "</p>"
            "<p>"
            "If you use ImpactSynth in your research, please cite the following work:<br>"
            "Boussot V., Dillenseger J.-L.:<br>"
            "<b>KonfAI: A Modular and Fully Configurable Framework for Deep Learning in Medical Imaging.</b><br>"
            '<a href="https://arxiv.org/abs/2508.09823">https://arxiv.org/abs/2508.09823</a>'
            "</p>"
        )


class ImpactSynthWidget(ScriptedLoadableModuleWidget):
    """
    Top-level scripted loadable module widget for KonfAI.

    This class ties together the Slicer module system with the KonfAICoreWidget,
    which handles actual application logic and GUI.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        super().__init__(parent)

    def setup(self) -> None:
        """
        Construct and initialize the module GUI.

        This method is called once when the user first opens the module.
        """
        super().setup()

        self.konfai_core = KonfAICoreWidget("Impact Synth")
        impact_synth_widget = KonfAIAppTemplateWidget("Synthesis", ["VBoussot/ImpactSynth"])
        impact_seg_widget = KonfAIAppTemplateWidget(
            "Segmentation", ["VBoussot/MRSegmentator-KonfAI", "VBoussot/TotalSegmentator-KonfAI"]
        )
        self.konfai_core.register_apps([impact_synth_widget, impact_seg_widget])
        self.layout.addWidget(self.konfai_core)

        if _is_reload_setup("SlicerImpactSynth"):
            self.konfai_core.enter()

    def cleanup(self) -> None:
        """
        Called when the application closes and the module widget is destroyed.
        """
        self.konfai_core.cleanup()

    def enter(self) -> None:
        """
        Called each time the user opens this module.

        This hook can be used to ensure state is up-to-date when the user
        returns to the module. Currently no additional logic is required.
        """
        self.konfai_core.enter()

    def exit(self) -> None:  # noqa: A003
        """
        Called each time the user navigates away from this module.

        This hook can be used to pause or finalize ongoing tasks, but
        no special handling is required at the moment.
        """
        self.konfai_core.exit()

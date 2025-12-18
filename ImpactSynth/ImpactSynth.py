from qt import QWidget
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import ScriptedLoadableModule, ScriptedLoadableModuleWidget
from slicer.util import VTKObservationMixin


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


class ImpactSynthWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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
        VTKObservationMixin.__init__(self)  # needed for parameter node observation

    def setup(self) -> None:
        """
        Construct and initialize the module GUI.

        This method is called once when the user first opens the module.
        """
        super().setup()
        from KonfAI import KonfAIAppTemplateWidget, KonfAICoreWidget

        self.konfai_core = KonfAICoreWidget("Impact Synth")
        impact_synth_widget = KonfAIAppTemplateWidget("Synthesis", ["VBoussot/ImpactSynth"])
        impact_seg_widget = KonfAIAppTemplateWidget(
            "Segmentation", ["VBoussot/MRSegmentator-KonfAI", "VBoussot/TotalSegmentator-KonfAI"]
        )
        self.konfai_core.register_apps([impact_synth_widget, impact_seg_widget])
        self.layout.addWidget(self.konfai_core)
        self.konfai_core.enter()

    def cleanup(self) -> None:
        """
        Called when the application closes and the module widget is destroyed.
        """
        self.removeObservers()
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

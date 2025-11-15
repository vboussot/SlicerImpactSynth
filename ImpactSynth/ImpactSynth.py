from qt import QWidget
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
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
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Synthesis")]
        self.parent.dependencies = ["KonfAI"]
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

class ImpactSynthWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation

    def setup(self) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)
        from KonfAI import KonfAICoreWidget, KonfAIAppTemplateWidget

        self.konfai_core = KonfAICoreWidget("Impact Synth")
        impactSynthWidget = KonfAIAppTemplateWidget("Synthesis", ["VBoussot/ImpactSynth"])
        impactSegWidget = KonfAIAppTemplateWidget("Segmentation", ["VBoussot/MRSegmentator-KonfAI"])
        self.konfai_core.register_konfai_apps([impactSynthWidget, impactSegWidget])
        self.layout.addWidget(self.konfai_core)
        
    def cleanup(self):
        """
        Called when the application closes and the module widget is destroyed.
        """
        pass

    def enter(self):
        """
        Called each time the user opens this module.
        """
        # Make sure parameter node exists and observed
        pass

    def exit(self):
        """
        Called each time the user opens a different module.
        """
        pass
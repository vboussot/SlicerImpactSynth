import slicer


class RegistrationTab:

    def __init__(self, ui_tab, logCallback, progressCallback):
        ui_tab.setMRMLScene(slicer.mrmlScene)
        self.ui = slicer.util.childWidgetVariables(ui_tab)
        self._parameterNode = None
        self._updatingGUIFromParameterNode = False
        self.ui.impactTransformSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.update_parameter_node_from_GUI)

    def updateGUIFromParameterNode(self, caller=None, event=None):
        pass

    def on_open_tab(self):
        pass

    def update_parameter_node_from_GUI(self, caller=None, event=None):
        """
        This method is called when the user makes any change in the GUI.
        The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
        """

        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return

        wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

        self._parameterNode.SetNodeReferenceID("ImpactTransform", self.ui.impactTransformSelector.currentNodeID)

        self._parameterNode.EndModify(wasModified)

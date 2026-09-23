cmake_minimum_required(VERSION 3.5)

project(ImpactSynth)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/vboussot/SlicerImpactSynth")
set(EXTENSION_CATEGORY "Image Synthesis")
set(EXTENSION_CONTRIBUTORS "Valentin Boussot (University of Rennes, France), Cédric Hémon (University of Rennes, France), Jean-Louis Dillenseger (University of Rennes, France)")
set(EXTENSION_DESCRIPTION "Synthetic CT from MRI or CBCT with the TotalSynth models, evaluation with or without a reference CT, and segmentation of the synthetic CT, powered by KonfAI.")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/vboussot/SlicerImpactSynth/main/ImpactSynth.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/vboussot/SlicerImpactSynth/main/Screenshots/main.png https://raw.githubusercontent.com/vboussot/SlicerImpactSynth/main/Screenshots/tutorial/03-sct.jpg https://raw.githubusercontent.com/vboussot/SlicerImpactSynth/main/Screenshots/tutorial/04-evaluation.jpg https://raw.githubusercontent.com/vboussot/SlicerImpactSynth/main/Screenshots/tutorial/06-segmentation.jpg")
set(EXTENSION_DEPENDS "KonfAI")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(ImpactSynth)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})

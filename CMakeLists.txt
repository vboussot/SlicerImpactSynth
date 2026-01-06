cmake_minimum_required(VERSION 3.5)

project(ImpactSynth)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/vboussot/SlicerImpactSynth")
set(EXTENSION_CATEGORY "Image Synthesis")
set(EXTENSION_CONTRIBUTORS "Valentin Boussot (University of Rennes, France), Cédric Hémon (University of Rennes, France), Jean-Louis Dillenseger (University of Rennes, France)")
set(EXTENSION_DESCRIPTION "Deep learning-based synthetic CT generation, sCT segmentation, and quality assurance tools powered by KonfAI IMPACT-Synth models.")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/vboussot/SlicerImpactSynth/main/ImpactSynth.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/vboussot/SlicerImpactSynth/main/docs/Synthesis.png" "https://raw.githubusercontent.com/vboussot/SlicerImpactSynth/main/docs/Segmentation.png" "https://raw.githubusercontent.com/vboussot/SlicerImpactSynth/main/docs/Evaluation.png")
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

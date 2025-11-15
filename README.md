# 🧠 Slicer IMPACT-Synth  

**Slicer IMPACT-Synth** is an open-source 3D Slicer extension designed for the generation of **synthetic CT (sCT)** images from **MRI** or **CBCT** in radiotherapy.  
It provides a dedicated integration of the IMPACT-Synth framework within the 3D Slicer environment, making advanced deep learning–based sCT generation as well as comprehensive quality-assurance (QA) tools accessible for routine clinical practice and research workflows in radiotherapy.

The extension leverages state-of-the-art models from the **SynthRAD 2025 Challenge [1]**, ranked *3rd* in both MRI→CT and CBCT→CT tasks, and is powered by **KonfAI [3]**, a modular deep learning framework ensuring **fast inference**, **reproducibility**, **flexible deployment**, and **seamless integration** into clinical workflows.

---

## 🖼️ Interface Overview

| sCT synthesis interface | Segmentation interface |
|-------------------------|------------------------|
| <img src="docs/Synthesis.png" alt="Synthesis interface" width="100%"> | <img src="docs/Segmentation.png" alt="Segmentation QA interface" width="100%"> |
| *Figure 1 – sCT synthesis.* | *Figure 2 – Anatomical segmentation.* |

<p align="center">
  <img src="docs/Evaluation.png" alt="Evaluation interface" width="45%"><br>
  <em>Figure 3 – Evaluation with reference.</em>
</p>
<p align="center">
  <strong>🎥 Video coming soon…</strong>
</p>

---

## ⚙️ Features

### 🧩 Deep Learning Inference
- sCT generation from MRI or CBCT volumes  
- Supports **DICOM RT**, **NIfTI** (`.nii`, `.nii.gz`), and **MHA** formats  
- Automatic preprocessing and intensity normalization  

### ⚕️ Quality Assurance (QA)
- Automatic segmentation of both input and generated volumes  
- Quantitative metrics: **Dice**, **HD95**, **MAE**, **PSNR**, **MS-SSIM**  
- Synchronized **2D/3D visual inspection** within Slicer  

### 📉 Uncertainty Quantification
- Ensemble and test-time augmentation (TTA) strategies  
- Visualization of **aleatoric** and **epistemic** uncertainty maps  
- Exportable maps for **dose propagation [2]**  

### 💡 Integration-Ready
- Direct connection with **PACS** and DICOM RT import  
- Automatic end-to-end pipeline execution  
- Future compatibility with **IMPACT-Reg** for **dose accumulation** workflows  

---

## 🚀 Installation

1. Install **3D Slicer ≥ 5.6**  
2. Clone this repository:
   ```bash
   git clone https://github.com/vboussot/SlicerImpactSynth.git
   ```
3. In Slicer, open:  
   **Edit → Application Settings → Modules → Additional Module Paths**  
   and add the folder `SlicerImpactSynth`
4. Restart Slicer and open the **IMPACT-Synth** module.

---

## 📊 Performance

| Metric | Abdomen | Head & Neck | Thorax | Mean |
|:-------|:---------|:-------------|:--------|:------|
| **MAE [HU]** | 49.7 | 52.0 | 44.0 | 48.6 |
| **PSNR [dB]** | 32.1 | 31.9 | 31.4 | 31.8 |
| **MS-SSIM** | 0.91 | 0.96 | 0.95 | 0.94 |

> Quantitative performance of IMPACT-Synth for CBCT→CT synthesis (SynthRAD2025 dataset).

---

## 📚 References

1. Thummerer, A. *et al.*, **SynthRAD2025 Grand Challenge dataset: Generating synthetic CTs for radiotherapy from head to abdomen.** *Med. Phys.*, 52(7), 2025.  
2. Hémon, C. *et al.*, **Modeling dose uncertainty in cone-beam computed tomography: Predictive approach for deep learning-based synthetic computed tomography generation.** *Phys. Imag. Rad. Oncol.*, 33, 2025.  
3. Boussot, V. & Dillenseger, J.-L., **KonfAI: A Modular and Fully Configurable Framework for Deep Learning in Medical Imaging.** *arXiv:2508.09823*, 2025.  
4. Boussot, V. *et al.*, **Why Registration Quality Matters: Enhancing sCT Synthesis with IMPACT-Based Registration.** *arXiv:2510.21358*, 2025.  
5. Boussot, V. *et al.*, **IMPACT: A Generic Semantic Loss for Multimodal Medical Image Registration.** *arXiv:2503.24121*, 2025.  

---

🎥 **Demonstration video and pretrained models:**  
[https://github.com/vboussot/SlicerImpactSynth](https://github.com/vboussot/SlicerImpactSynth)

---

*Slicer IMPACT-Synth provides an open, transparent, and extensible environment for synthetic CT generation and QA in adaptive radiotherapy — bridging deep learning and clinical usability within 3D Slicer.*


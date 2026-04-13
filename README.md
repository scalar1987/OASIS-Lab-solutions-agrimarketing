# 🌱 OASIS Vision — AI-Powered Crop Disease Diagnosis System

> **O**pen **A**gricultural **S**mart **I**nspection **S**ystem  
> Instant crop disease diagnosis and treatment recommendations from a single smartphone photo

---

## 📌 Overview

Crop disease diagnosis in Korean farms still heavily relies on visual inspection and expert visits.  
OASIS Vision is an AI solution that enables **on-site, real-time diagnosis** using a deep learning image classification model.

- 🎯 Target Users: Korean farmers and agricultural workers with smartphones
- 🌾 Supported Crops: Pepper, Paprika, Tomato, Apple, Grape (expanding)
- 📊 How It Works: Capture a photo of a leaf or fruit → AI classifies disease → Treatment provided

---

## ✨ Features

| Feature | Description | Status |
|---------|-------------|--------|
| 📸 Disease Diagnosis | Classifies crop disease from photo + confidence score | ✅ Done |
| 💊 Treatment Recommendation | Pesticide prescription based on official NCPMS data (PLS compliant) | ✅ Done |
| 🌿 Growth Stage Tracking | Auto-calculates current growth stage from planting date | ✅ Done |
| 🌐 Gradio Web App | Browser-based MVP — no installation required | ✅ Done |
| 📱 Flutter Mobile App | Camera + GPS + push notifications integration | 🔄 Planned |
| 🔔 Proactive Alerts | Early disease risk warnings based on weather conditions | 🔄 Planned |

---

## 🧠 AI Model

| Item | Details |
|------|---------|
| Architecture | EfficientNet-B3 (Transfer Learning) |
| Training Data | PlantVillage 33,708 images + AI Hub 24,121 images |
| Classes | 18 (Pepper ×2, Apple ×4, Grape ×4, Tomato ×8) |
| Validation Accuracy | **99.9%** |
| Training Environment | Google Colab T4 GPU |

---

## 🗂️ Datasets

### PlantVillage (Base Training)
- Source: Kaggle PlantVillage Dataset
- Size: 33,708 images (18 classes)
- Note: US-based images

### AI Hub Plant Disease Integrated Dataset (Korea-specific)
- Source: [AI Hub](https://aihub.or.kr) — #104 Plant Disease Integrated Data
- Size: 24,121 images (Validation source data)
- Categories:

  | Folder | Crop | Type | Images |
  |--------|------|------|--------|
  | VS1 | Pepper | Diseased | 2,573 |
  | VS4 | Pepper | Healthy | 5,515 |
  | VS17 | Tomato | Diseased | 2,615 |
  | VS20 | Tomato | Healthy | 5,410 |
  | VS21 | Paprika | Diseased | 2,954 |
  | VS24 | Paprika | Healthy | 5,054 |

---

## 🏗️ Project Structure

```
오아시스Vision/
├── README.md
├── CLAUDE.md                       # Claude Code context file
├── .mcp.json                       # MCP server configuration
│
├── create_manifest.py              # Dataset manifest generation script
├── manifest.csv                    # Full image list
├── manifest.json                   # Dataset info in JSON format
├── dataset_statistics.txt          # Dataset statistics report
│
└── app_vision_todo.md              # Development roadmap & progress
```

---

## 🛠️ Tech Stack

### AI / ML
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat&logo=pytorch&logoColor=white)
![timm](https://img.shields.io/badge/timm-EfficientNet-orange?style=flat)

### Web (MVP)
![Gradio](https://img.shields.io/badge/Gradio-FF7C00?style=flat)
![Google Colab](https://img.shields.io/badge/Google_Colab-F9AB00?style=flat&logo=googlecolab&logoColor=white)

### Mobile App (Planned)
![Flutter](https://img.shields.io/badge/Flutter-02569B?style=flat&logo=flutter&logoColor=white)
![Firebase](https://img.shields.io/badge/Firebase-FFCA28?style=flat&logo=firebase&logoColor=black)

### Data / APIs
- Korea Meteorological Administration Short-term Forecast API
- NCPMS National Crop Pest Management System API
- Kakao Maps API

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/{username}/oasis-vision.git
cd oasis-vision
```

### 2. Install Dependencies

```bash
pip install torch torchvision timm gradio
```

### 3. Prepare Model Files

> You need the trained model file (`oasis_v1_best.pt`) and class mapping (`class_names.json`).  
> Download from Google Drive → `OASIS_Vision/Models/`

### 4. Run the Gradio App

```python
# Run locally or in Colab
python app.py
# Or in a Colab notebook: app.launch(share=True)
```

---

## 📈 Roadmap

```
[Gradio MVP — Model Validation Phase]
PHASE 0 — Environment Setup        ✅ Done
PHASE 1 — Data Preparation         ✅ Done (57,829 images total)
PHASE 2 — Model Training           ✅ Done (Val Accuracy: 99.9%)
PHASE 3 — Treatment DB             ✅ Done (NCPMS official data, 14 classes)
PHASE 4 — Gradio Web MVP           ✅ Done (diagnosis + treatment working)
PHASE 5 — Testing & Feedback       ← Current

[Flutter App — Productization Phase]
PHASE 6 — Flutter App              (Camera + GPS + history log + push alerts)
PHASE 7 — Crop Expansion (15 types)
PHASE 8 — Sensor Node Integration  (OASIS Lab hardware)
```

---

## ⚠️ Known Limitations

- **Paprika misclassification**: Only 2 PlantVillage classes → improvement planned with AI Hub data fine-tuning
- **Leaf curl & virus symptoms undetected**: These classes are absent from training data → field photo collection needed
- **Greenhouse overview shots**: Model is optimized for close-up leaf/fruit photos — wide-angle shots may misclassify

---

## 📄 References

- [AI Hub Plant Disease Integrated Dataset](https://aihub.or.kr)
- [NCPMS National Crop Pest Management System](https://ncpms.rda.go.kr)
- [PlantVillage Dataset (Kaggle)](https://www.kaggle.com/datasets/emmarex/plantdisease)
- [EfficientNet Paper](https://arxiv.org/abs/1905.11946)

---

## 👤 Developer

**OASIS Lab** — Smart Agriculture AI Solutions

---

*This project is actively maintained. Feel free to open an Issue for feedback or questions.*

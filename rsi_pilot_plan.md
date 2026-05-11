# RSI Pilot — WMA Detectability via Microstructural Signature

> Objectif: tester si les maps RSI (RNI, RND, FNI) distinguent les sujets WMA+ des sujets sains au baseline.

---

## Pipeline Overview

```
DWI (multi-shell) → extract b0 → SynthStrip (skull-strip) → brain mask → pyrsi → RSI maps
```

Tools:
- **SynthStrip** (`synthstrip_v1.8.sif`): robust skull-stripping from b0
- **pyrsi** (`pyrsi.sif`): RSI decomposition (RNI, RND, RNT, FNI)

Both containers live at `/mnt/fac/CX500002_DS1/lab-utils/`.

---

## Data

All data from ABCD 6.1 mproc, baseline ses-00A.

### WMA+ subjects (6, mrif_score=3)

| Subject ID | NDAR | Key finding |
|---|---|---|
| sub-9PJ7VRDA | NDAR_INV9PJ7VRDA | Supratentorial WM T2 hyperintensities |
| sub-61PF7E1L | NDAR_INV61PF7E1L | 5mm ovoid T2/T1 lesion in left medulla |
| sub-80VAXPN1 | NDAR_INV80VAXPN1 | T2 hyperintensity bilateral frontal horns |
| sub-93JXKKF3 | NDAR_INV93JXKKF3 | Left frontal periventricular WM lesion |
| sub-99TVX9G8 | NDAR_INV99TVX9G8 | Multiple supratentorial WM T2 hyperintensities |
| sub-701F04JM | NDAR_INV701F04JM | Confluent frontal/parietal WM lesions |

### Healthy subjects (6, mrif_score=1)

| Subject ID | NDAR |
|---|---|
| sub-2HLV1V0P | NDAR_INV2HLV1V0P |
| sub-2HLV10CC | NDAR_INV2HLV10CC |
| sub-2HLZM8RB | NDAR_INV2HLZM8RB |
| sub-2J3D85NJ | NDAR_INV2J3D85NJ |
| sub-2JB8MUAJ | NDAR_INV2JB8MUAJ |
| sub-2K3JH38W | NDAR_INV2K3JH38W |

### Paths

```
Pilot symlinks: /mnt/fac/CX500007_DS1/bardou/rsi-wma/pilot_data/{WMA,nonWMA}/sub-XXX/
Source:         /mnt/fac/CX500007_DS1/ABCD/6.1/imaging/derivatives/mproc/sub-XXX/ses-00A/
Containers:     /mnt/fac/CX500002_DS1/lab-utils/{synthstrip_v1.8.sif,pyrsi.sif}
Output:         /mnt/fac/CX500007_DS1/bardou/rsi-wma/rsi_output/sub-XXX/
```

---

## Etape 1 — Compute RSI maps

**Script**: `run_rsi_pilot.py`

Pipeline per subject:
1. Load DWI, average b0 volumes (b ≤ 10)
2. Skull-strip b0 with SynthStrip → `brain_mask.nii.gz`
3. Run pyrsi with mask → `rsi/RNI.nii.gz`, `rsi/RND.nii.gz`, `rsi/RNT.nii.gz`, `rsi/FNI.nii.gz`

```bash
cd /mnt/fac/CX500007_DS1/bardou/rsi-wma
python run_rsi_pilot.py
```

Output structure:
```
rsi_output/
├── sub-9PJ7VRDA/
│   ├── b0_mean.nii.gz
│   ├── brain_mask.nii.gz
│   └── rsi/
│       ├── RNI.nii.gz
│       ├── RND.nii.gz
│       ├── RNT.nii.gz
│       └── FNI.nii.gz
├── sub-61PF7E1L/
│   └── ...
└── ...
```

---

## Etape 2 — Segmentation manuelle des WMA (ITK-SNAP)

Pour les 6 WMA+ uniquement. Segmenter sur T1+T2 (jamais sur RSI — biais circulaire).

1. Espace: T1 natif
2. Inclusion: hyperintense T2, hypo/iso T1, visible 2 plans, ≥3 voxels, substance blanche
3. Exclusion: espaces périvasculaires, myélinisation tardive péri-trigonale, artefacts
4. Outil: ITK-SNAP, T1 principal, T2 overlay

```bash
itksnap -g sub-XX_T1w.nii.gz -o sub-XX_T2w.nii.gz
# Sauvegarder → rsi_output/sub-XX/lesion_mask.nii.gz
```

Validation: re-segmenter 2 patients à J+7 → Dice intra-rater ≥ 0.7.

---

## Etape 3 — Registration masques → espace DWI

Les masques sont en espace T1, les RSI maps en espace DWI.

```bash
flirt -in sub-XX_T1w.nii.gz -ref sub-XX/b0_mean.nii.gz \
      -omat T1_to_dwi.mat -dof 6 -cost normmi

flirt -in sub-XX/lesion_mask.nii.gz -ref sub-XX/b0_mean.nii.gz \
      -applyxfm -init T1_to_dwi.mat \
      -interp nearestneighbour \
      -out sub-XX/lesion_in_dwi.nii.gz
```

---

## Etape 4 — Extraction des métriques RSI

Pour chaque WMA+: valeurs RSI dans lésion vs NAWM (WM mask - lésion).
Pour chaque contrôle: valeurs RSI dans toute la WM.

Métriques: RNI, RND, FNI.

Output: `rsi_lesion_analysis.csv`

---

## Etape 5 — Analyses statistiques

### 5.1 Intra-patient: lésion vs NAWM
- Wilcoxon signed-rank (paired, n=6)
- Direction attendue: lésion → RNI↑, RND↓, FNI↑

### 5.2 Inter-groupe: NAWM(WMA+) vs WM(Ctrl)
- Mann-Whitney U
- Si NAWM diffère → RSI détecte du pathologique invisible en T1/T2

### 5.3 Figures
- Violin plot: WM ctrl | NAWM WMA+ | Lésion WMA+
- Cas illustratif: T1 | T2 | RNI | RND | FNI avec contour lésionnel
- ROC: classification lésion vs NAWM par métrique RSI

---

## RSI Compartments Reference

| Compartment | Isotropic | Directional |
|---|---|---|
| Restricted (intracellular) | RNI | RND |
| Hindered (extracellular) | HNI | HND |
| Free (CSF) | FNI | — |

WMA relevance:
- **RNI↑** = gliosis/inflammation (cellular proliferation)
- **RND↓** = demyelination/axonal loss
- **FNI↑** = edema, tissue breakdown

---

## Go / No-Go (après étape 5)

- **Go**: différence significative lésion vs NAWM (p < 0.05) et/ou NAWM ≠ WM ctrl
- **Super-go**: NAWM diffère en RSI alors que normale en T1/T2 → RSI détecte du "pré-lésionnel"
- **No-go**: aucune différence → pivot

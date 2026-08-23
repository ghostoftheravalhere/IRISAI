# IRIS AI V4 — Dataset Qualification & Quality Report

## Executive Summary

- **Status**: **NO USABLE GAZE DATASET AVAILABLE**
- **Date**: 2026-08-15
- **Evaluator**: Gaze Dataset Validator Service (`GazeDatasetValidator`)
- **Target Directory**: `dataset/gaze/`

---

## Dataset Metrics Summary

| Metric | Measured Value | Requirement | Status |
| :--- | :--- | :--- | :--- |
| **Total Users** | 0 | $\ge 10$ multi-user subjects | **NON-COMPLIANT (0)** |
| **Total Sessions** | 0 | $\ge 15$ sessions across users | **NON-COMPLIANT (0)** |
| **Total Samples** | 0 | $\ge 2,700$ samples (30/target/user) | **NON-COMPLIANT (0)** |
| **Target Grid** | 9-Point Grid | 9-point screen grid | Compliant Schema |
| **Eye Crop Size** | $64 \times 64$ px | Dual-eye PNG $64 \times 64$ px | Compliant Schema |
| **Validation Status** | No data files | 0 corrupted, 0 missing | Empty Dataset |

---

## Samples per Target Distribution

| Target Index | Name | Target $(X, Y)$ | Sample Count | Target Status |
| :---: | :--- | :---: | :---: | :---: |
| **0** | top-left | $(0.1, 0.1)$ | 0 | Missing |
| **1** | top-center | $(0.5, 0.1)$ | 0 | Missing |
| **2** | top-right | $(0.9, 0.1)$ | 0 | Missing |
| **3** | middle-left | $(0.1, 0.5)$ | 0 | Missing |
| **4** | center | $(0.5, 0.5)$ | 0 | Missing |
| **5** | middle-right | $(0.9, 0.5)$ | 0 | Missing |
| **6** | bottom-left | $(0.1, 0.9)$ | 0 | Missing |
| **7** | bottom-center | $(0.5, 0.9)$ | 0 | Missing |
| **8** | bottom-right | $(0.9, 0.9)$ | 0 | Missing |

---

## Detailed Data Integrity Checks

- **Rejected Samples**: 0
- **Invalid Json Lines**: 0
- **Missing / Unreadable Eye Images**: 0
- **Duplicate Sample IDs**: 0
- **Out-of-Bounds Target Coordinates**: 0
- **Class / Target Imbalance Ratio**: N/A (0 samples)

---

## User-Level Split Strategy (Future Recommendation)

When physical dataset collection is executed across $N$ subjects, data splitting **MUST** occur strictly by `user_id` to prevent data leakage:

```text
               Full Collected Multi-User Dataset (N Users)
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
   Train Set (~67%)        Validation Set (~20%)       Test Set (~13%)
  (Users 01 to 10)         (Users 11 to 13)         (Users 14 to 15)
```

- **Random image-level splitting is strictly prohibited** because consecutive video frames from the same subject/head-pose would contaminate validation and test sets.

---

## Task Readiness Determination

- **TASK-003 Status**: **BLOCKED / REQUIRES PHYSICAL DATA COLLECTION**
- **TASK-004 (Deep Learning Model Training)**: **CANNOT BEGIN**

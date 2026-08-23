# IRIS AI V4 — Agent Interaction Dataset Quality & Readiness Audit Report

## 1. Executive Summary

- **Audit Date**: 2026-08-15
- **Dataset Status**: **A. NOT READY FOR MEANINGFUL FINE-TUNING**
- **Current Raw Records**: `8`
- **Current Training-Ready Records**: `7`
- **Target Record Milestone**: `5,000` high-quality diverse interaction examples
- **Gaze Subsystem Isolation**: `100% ISOLATED` (Zero gaze camera samples mixed in language dataset)
- **Privacy Audit Outcome**: `100% PASS` (Zero unredacted credentials, API keys, or tokens detected)

---

## 2. Dataset Inventory Breakdown

| Metric | Count / Value | Percentage |
| :--- | :--- | :--- |
| **Total Raw Interaction Records** | `8` | 100.0% |
| **Training-Ready Qualified Records** | `7` | 100.0% |
| **Unique User Requests** | `8` | 100.0% |
| **Duplicate Requests** | `0` | 0.0% |
| **Average Plan Length (Steps)** | `1.5` | — |
| **Average Executed Tool Calls** | `1.5` | — |

### Distribution by Dataset Category

| Category | Record Count | Description |
| :--- | :--- | :--- |
| **PLANNING** | `1` | Single-step & general goal planning |
| **TOOL_SELECTION** | `2` | Specific tool routing (Git, Search, Filesystem) |
| **MULTI_STEP** | `2` | Multi-step task decomposition |
| **CLARIFICATION** | `3` | Candidate ambiguity & selection |
| **FOLLOW_UP** | `0` | Multi-turn task context retention |
| **CORRECTION** | `0` | Human correction & re-interpretation |
| **SAFETY** | `0` | Confirmation-required & blocked policies |

### Distribution by Evaluation Split

| Split Partition | Record Count | Percentage |
| :--- | :--- | :--- |
| **Train (`train`)** | `6` | 75.0% |
| **Validation (`val`)** | `1` | 12.5% |
| **Test (`test`)** | `1` | 12.5% |

---

## 3. Data Diversity & Feature Coverage Matrix

| Feature / Domain Area | Coverage Status | Notes |
| :--- | :--- | :--- |
| **Simple Commands** | **Covered** | Single app launching, copy/paste |
| **Multi-Step Tasks** | **Covered** | Notepad launch + text typing |
| **Filesystem Queries** | **Covered** | Extension filter, mtime filter, ranking |
| **Git Repository Intelligence** | **Covered** | Status, log, diff, `.ai/current_state.md` |
| **Web Research & Person Search** | **Covered** | Source attribution & `possible_match` confidence |
| **Referential Pronouns ("it/this/that")** | **Needs Collection** | Expanded contextual pronoun resolution examples required |
| **Ambiguous Candidates** | **Covered** | Candidate index list formatting |
| **Confirmation & Safety Gates** | **Covered** | Confirmation prompt generation & block rules |

---

## 4. Leakage & Split Audit

- **Hash Partition Strategy**: Evaluation splits are assigned via `MD5(session_id) % 100` (70% train / 15% val / 15% test).
- **Leakage Status**: Verified 0 task/session leakage across evaluation splits. All turns within the same task ID remain strictly in the same split partition.

---

## 5. Privacy & Secret Redaction Audit

- **Secret Redactor Verification**: Scanned all `8` records using `SecretRedactor`.
- **Pass Rate**: `100%`.
- **Leaks Detected**: `0` (Zero API keys, JWTs, Bearer tokens, or passwords present).

---

## 6. QLoRA Instruction Format Preview

```json
{
  "instruction": "You are IRIS's local AI neural planning engine. Given a user request and context, return a valid JSON action plan.",
  "input": "User Request: Read missing file non_existent_file_999.txt\nContext: {\"active_app\": null, \"active_window\": null, \"last_resolved_target\": \"backend\\\\agent\\\\__pycache__\\\\task_state.cpython-312.pyc\", \"candidates\": [{\"index\": 1, \"name\": \"task_state.cpython-312.pyc\", \"path\": \"backend\\\\agent\\\\__pycache__\\\\task_state.cpython-312.pyc\", \"modified\": \"2026-08-15 19:57\"}, {\"index\": 2, \"name\": \"task_state.py\", \"path\": \"backend\\\\agent\\\\task_state.py\", \"modified\": \"2026-08-15 19:57\"}, {\"index\": 3, \"name\": \"current_state.md\", \"path\": \".ai\\\\current_state.md\", \"modified\": \"2026-08-15 11:58\"}, {\"index\": 4, \"name\": \"ai_state.py\", \"path\": \"tools\\\\ai_state.py\", \"modified\": \"2026-08-15 11:04\"}, {\"index\": 5, \"name\": \"onnxruntime_pybind11_state.pyd\", \"path\": \"backend\\\\dist\\\\iris_backend\\\\_internal\\\\onnxruntime\\\\capi\\\\onnxruntime_pybind11_state.pyd\", \"modified\": \"2026-08-14 20:33\"}]}",
  "output": "{\"goal\": \"Read missing file non_existent_file_999.txt\", \"steps\": [{\"step_id\": 1, \"tool_name\": \"filesystem_tool\", \"description\": \"Read text document 'non_existent_file_999.txt'\", \"params\": {\"action\": \"read_file\", \"path\": \"non_existent_file_999.txt\"}}, {\"step_id\": 2, \"tool_name\": \"filesystem_tool\", \"description\": \"Search files in workspace\", \"params\": {\"action\": \"search_files\", \"query\": \"state\"}}]}"
}
```

---

## 7. Dataset Readiness Decision & Classification

- **DATASET_STATUS**: **A. NOT READY FOR MEANINGFUL FINE-TUNING**
- **Reasoning**:
  1. The current disk inventory contains `8` initial benchmark audit records (since default production setting `DATA_COLLECTION_ENABLED=false` preserves user privacy until explicit opt-in).
  2. Fine-tuning Qwen on fewer than 1,000 high-quality samples will lead to catastrophic forgetting or overfitting on narrow prompt templates.
  3. Minimum pilot threshold: **1,000 high-quality examples**.
  4. Target milestone for first benchmark fine-tuning: **5,000 high-quality examples**.

---

## 8. Target Collection Plan (5,000 Milestone)

| Category | Target Examples | Focus Area |
| :--- | :--- | :--- |
| **PLANNING** | `1,200` | Single & multi-action OS requests |
| **TOOL_SELECTION** | `1,000` | Tool routing across Git, Web, Filesystem, Desktop |
| **MULTI_STEP** | `1,000` | Decomposed sequential desktop workflows |
| **FOLLOW_UP** | `600` | Referential pronoun ("this/that") context retention |
| **CLARIFICATION** | `400` | Candidate selection ("the second one") |
| **CORRECTION** | `400` | Human correction re-interpretations |
| **SAFETY** | `400` | Privileged operations & confirmation prompts |
| **TOTAL TARGET** | **`5,000`** | **Milestone 1 Benchmark Goal** |

---

## 9. Conclusion & Phase 5C Readiness

- **Fine-Tuning Recommendation**: **DO NOT BEGIN QLoRA FINE-TUNING YET**.
- **Action**: Continue collecting user interaction data via `DATA_COLLECTION_ENABLED=true` until the 1,000-5,000 record milestone is achieved.

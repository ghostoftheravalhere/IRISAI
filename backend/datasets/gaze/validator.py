"""Eye Gaze Dataset Validator Service."""

from __future__ import annotations

import json
from pathlib import Path

import cv2

from backend.datasets.gaze.schema import DatasetSummaryReport
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GazeDatasetValidator:
    """Scans gaze dataset hierarchy, checks image/metadata integrity, and generates summary report."""

    def __init__(self, base_dir: Path | str = "dataset/gaze") -> None:
        self._base_dir = Path(base_dir)

    def validate_dataset(self) -> DatasetSummaryReport:
        """Scan dataset directory, verify sample integrity, detect issues, and return report."""
        report = DatasetSummaryReport()
        if not self._base_dir.exists():
            report.is_valid = False
            report.issues.append("Dataset base directory does not exist.")
            return report

        user_dirs = list(self._base_dir.glob("user_*"))
        report.total_users = len(user_dirs)

        seen_sample_ids: set[str] = set()

        for user_dir in user_dirs:
            session_dirs = list(user_dir.glob("session_*"))
            report.total_sessions += len(session_dirs)

            for session_dir in session_dirs:
                metadata_file = session_dir / "metadata.jsonl"
                if not metadata_file.exists():
                    report.invalid_samples += 1
                    report.issues.append(f"Missing metadata.jsonl in {session_dir}")
                    continue

                with open(metadata_file, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, start=1):
                        line_str = line.strip()
                        if not line_str:
                            continue

                        try:
                            data = json.loads(line_str)
                        except Exception:
                            report.invalid_samples += 1
                            report.issues.append(f"Corrupted JSON on line {line_num} in {metadata_file}")
                            continue

                        sample_id = data.get("sample_id")
                        if not sample_id or sample_id in seen_sample_ids:
                            report.invalid_samples += 1
                            report.issues.append(f"Duplicate or missing sample_id '{sample_id}' in {metadata_file}")
                        else:
                            seen_sample_ids.add(sample_id)

                        # Validate target coordinates
                        target_x = data.get("target_x", -1.0)
                        target_y = data.get("target_y", -1.0)
                        if not (0.0 <= target_x <= 1.0 and 0.0 <= target_y <= 1.0):
                            report.invalid_samples += 1
                            report.issues.append(f"Invalid target coordinates ({target_x}, {target_y}) in sample {sample_id}")

                        # Check image files exist and are readable
                        left_rel = data.get("left_image", "")
                        right_rel = data.get("right_image", "")
                        left_path = session_dir / left_rel
                        right_path = session_dir / right_rel

                        if not left_path.exists() or cv2.imread(str(left_path)) is None:
                            report.missing_images += 1
                            report.issues.append(f"Missing or corrupted left image: {left_path}")

                        if not right_path.exists() or cv2.imread(str(right_path)) is None:
                            report.missing_images += 1
                            report.issues.append(f"Missing or corrupted right image: {right_path}")

                        t_idx = data.get("target_index", 0)
                        report.samples_per_target[t_idx] = report.samples_per_target.get(t_idx, 0) + 1
                        report.total_samples += 1

        if report.issues:
            report.is_valid = len(report.issues) == 0

        logger.info("Validated gaze dataset: users=%d, samples=%d, valid=%s", report.total_users, report.total_samples, report.is_valid)
        return report

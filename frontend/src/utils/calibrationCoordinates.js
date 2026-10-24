/**
 * Calibration coordinate and UI helpers for IRIS AI.
 *
 * Backend coordinate convention:
 * - Screen origin (0, 0) is at the TOP-LEFT.
 * - Normalized X increases rightward in [0.0, 1.0].
 * - Normalized Y increases downward in [0.0, 1.0].
 * - Frontend CSS positioning maps:
 *     left = (x * 100)%
 *     top  = (y * 100)%
 *   with transform: translate(-50%, -50%) to center target dots.
 * - No vertical inversion or double mirroring is applied to target placement.
 */

export const DEFAULT_16POINT_TRAINING_GRID = [
  { index: 0, x: 0.1000, y: 0.1000 },
  { index: 1, x: 0.3667, y: 0.1000 },
  { index: 2, x: 0.6333, y: 0.1000 },
  { index: 3, x: 0.9000, y: 0.1000 },
  { index: 4, x: 0.1000, y: 0.3667 },
  { index: 5, x: 0.3667, y: 0.3667 },
  { index: 6, x: 0.6333, y: 0.3667 },
  { index: 7, x: 0.9000, y: 0.3667 },
  { index: 8, x: 0.1000, y: 0.6333 },
  { index: 9, x: 0.3667, y: 0.6333 },
  { index: 10, x: 0.6333, y: 0.6333 },
  { index: 11, x: 0.9000, y: 0.6333 },
  { index: 12, x: 0.1000, y: 0.9000 },
  { index: 13, x: 0.3667, y: 0.9000 },
  { index: 14, x: 0.6333, y: 0.9000 },
  { index: 15, x: 0.9000, y: 0.9000 },
];

export const DEFAULT_4POINT_VALIDATION_GRID = [
  { index: 16, x: 0.2333, y: 0.7667 },
  { index: 17, x: 0.7667, y: 0.7667 },
  { index: 18, x: 0.5000, y: 0.5000 },
  { index: 19, x: 0.2333, y: 0.2333 },
];

export const DEFAULT_9POINT_GRID = [
  { index: 0, x: 0.10, y: 0.10 },
  { index: 1, x: 0.50, y: 0.10 },
  { index: 2, x: 0.90, y: 0.10 },
  { index: 3, x: 0.10, y: 0.50 },
  { index: 4, x: 0.50, y: 0.50 },
  { index: 5, x: 0.90, y: 0.50 },
  { index: 6, x: 0.10, y: 0.90 },
  { index: 7, x: 0.50, y: 0.90 },
  { index: 8, x: 0.90, y: 0.90 },
];

/**
 * Calculate CSS positioning styles for a normalized coordinate target.
 * Verifies screen origin (0, 0) top-left, normalized Y increases downward,
 * no vertical inversion, and no double mirroring.
 */
export function getTargetPosition(point) {
  if (!point || typeof point.x !== "number" || typeof point.y !== "number") {
    return { left: "50%", top: "50%" };
  }
  const leftPct = (point.x * 100).toFixed(3);
  const topPct = (point.y * 100).toFixed(3);
  return {
    left: `${leftPct}%`,
    top: `${topPct}%`,
  };
}

/**
 * Resolve location description (quadrant/side) for a point.
 */
export function getPointQuadrant(x, y) {
  const horizontal = x < 0.35 ? "Left" : x > 0.65 ? "Right" : "Center";
  const vertical = y < 0.35 ? "Top" : y > 0.65 ? "Bottom" : "Middle";
  if (horizontal === "Center" && vertical === "Middle") return "Center";
  return `${vertical} ${horizontal}`;
}

/**
 * Split backend points into mode, training points, and validation points.
 */
export function splitTargetsByMode(backendPoints, totalPointsFromProgress = 20) {
  const points = Array.isArray(backendPoints) && backendPoints.length > 0 ? backendPoints : null;

  if (points) {
    if (points.length === 20) {
      return {
        mode: "16-point",
        trainingPoints: points.slice(0, 16),
        validationPoints: points.slice(16, 20),
        allPoints: points,
      };
    }
    if (points.length === 9) {
      return {
        mode: "9-point",
        trainingPoints: points.slice(0, 9),
        validationPoints: [],
        allPoints: points,
      };
    }
  }

  // Fallback based on total points
  if (totalPointsFromProgress === 9) {
    return {
      mode: "9-point",
      trainingPoints: DEFAULT_9POINT_GRID,
      validationPoints: [],
      allPoints: DEFAULT_9POINT_GRID,
    };
  }

  return {
    mode: "16-point",
    trainingPoints: DEFAULT_16POINT_TRAINING_GRID,
    validationPoints: DEFAULT_4POINT_VALIDATION_GRID,
    allPoints: [...DEFAULT_16POINT_TRAINING_GRID, ...DEFAULT_4POINT_VALIDATION_GRID],
  };
}

/**
 * Check whether calibration is strictly authorized by backend.
 * Never grant authorization on client side without backend confirmation.
 */
export function isCalibrationAuthorized(progress, expectedMode = null) {
  if (!progress) return false;
  // Must be complete AND explicitly authorized by backend
  if (!progress.complete || !progress.is_calibrated) {
    return false;
  }
  // Check mode alignment if an expected mode is specified
  if (expectedMode) {
    const actualMode = progress.mode || (progress.total_points === 9 ? "9-point" : "16-point");
    if (actualMode !== expectedMode) {
      return false;
    }
  }
  // 16-point calibration requires an explicit passing validation report
  const is16Point = progress.mode === "16-point" || progress.total_points === 20;
  if (is16Point) {
    if (!progress.validation_report || progress.validation_report.passed !== true) {
      return false;
    }
  }
  // If validation report is present, gates must have passed
  if (progress.validation_report && progress.validation_report.passed === false) {
    return false;
  }
  // If quality report recommends recalibration, not authorized
  if (progress.quality && progress.quality.recommend_recalibration === true) {
    return false;
  }
  return true;
}

/**
 * Clamp a panel's (x, y) position so it remains completely within the viewport bounds.
 *
 * @param {{ x: number, y: number }} desiredPos - Desired top-left corner
 * @param {{ width: number, height: number }} panelSize - Dimensions of the panel
 * @param {{ width: number, height: number }} viewportSize - Dimensions of the viewport
 * @param {number} [margin=12] - Safe inset from viewport boundaries
 * @returns {{ x: number, y: number }} Clamped coordinates
 */
export function clampPanelPosition(desiredPos, panelSize, viewportSize, margin = 12) {
  const pWidth = panelSize?.width || 360;
  const pHeight = panelSize?.height || 260;
  const vWidth = viewportSize?.width || (typeof window !== "undefined" ? window.innerWidth : 1920);
  const vHeight = viewportSize?.height || (typeof window !== "undefined" ? window.innerHeight : 1080);

  const minX = margin;
  const minY = margin;
  const maxX = Math.max(margin, vWidth - pWidth - margin);
  const maxY = Math.max(margin, vHeight - pHeight - margin);

  const x = Math.min(Math.max(desiredPos?.x ?? minX, minX), maxX);
  const y = Math.min(Math.max(desiredPos?.y ?? minY, minY), maxY);

  return { x: Math.round(x), y: Math.round(y) };
}

/**
 * Compute the default non-colliding floating panel placement based on the active target location.
 * If the active target is in the bottom-right quadrant, dock to the bottom-left.
 * Otherwise, dock to the bottom-right.
 *
 * @param {{ x: number, y: number }|null} activePoint - Normalized target coordinates [0.0, 1.0]
 * @param {{ width: number, height: number }} panelSize - Floating panel dimensions
 * @param {{ width: number, height: number }} viewportSize - Viewport dimensions
 * @param {number} [margin=24] - Screen margin
 * @returns {{ x: number, y: number, docked: 'bottom-left'|'bottom-right' }} Default position
 */
export function getDefaultPanelPosition(activePoint, panelSize, viewportSize, margin = 24) {
  const pWidth = panelSize?.width || 360;
  const pHeight = panelSize?.height || 260;
  const vWidth = viewportSize?.width || (typeof window !== "undefined" ? window.innerWidth : 1920);
  const vHeight = viewportSize?.height || (typeof window !== "undefined" ? window.innerHeight : 1080);

  // Collision avoidance: if active target is near bottom-right (x >= 0.55, y >= 0.55),
  // place the controller in the bottom-left corner to avoid occluding the gaze fixation point.
  const isBottomRightTarget = Boolean(
    activePoint &&
    typeof activePoint.x === "number" &&
    typeof activePoint.y === "number" &&
    activePoint.x >= 0.55 &&
    activePoint.y >= 0.55
  );

  const y = Math.max(margin, vHeight - pHeight - margin);
  if (isBottomRightTarget) {
    return {
      x: margin,
      y: Math.round(y),
      docked: "bottom-left",
    };
  }

  const x = Math.max(margin, vWidth - pWidth - margin);
  return {
    x: Math.round(x),
    y: Math.round(y),
    docked: "bottom-right",
  };
}

/**
 * Calculate absolute pixel coordinates of a normalized target point within a given viewport size.
 * Useful for layout verification and geometry assertions.
 *
 * @param {{ x: number, y: number }} point - Normalized coordinate point [0.0, 1.0]
 * @param {{ width: number, height: number }} viewportSize - Pixel dimensions of the calibration surface
 * @returns {{ pixelX: number, pixelY: number }}
 */
export function calculateTargetPixelPosition(point, viewportSize) {
  if (!point || typeof point.x !== "number" || typeof point.y !== "number") {
    return {
      pixelX: (viewportSize?.width || 1920) / 2,
      pixelY: (viewportSize?.height || 1080) / 2,
    };
  }
  const vWidth = viewportSize?.width || 1920;
  const vHeight = viewportSize?.height || 1080;
  return {
    pixelX: parseFloat((point.x * vWidth).toFixed(2)),
    pixelY: parseFloat((point.y * vHeight).toFixed(2)),
  };
}


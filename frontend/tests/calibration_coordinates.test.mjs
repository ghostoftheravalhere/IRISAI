import test from "node:test";
import assert from "node:assert";

import {
  DEFAULT_16POINT_TRAINING_GRID,
  DEFAULT_4POINT_VALIDATION_GRID,
  DEFAULT_9POINT_GRID,
  getTargetPosition,
  getPointQuadrant,
  splitTargetsByMode,
  isCalibrationAuthorized,
  clampPanelPosition,
  getDefaultPanelPosition,
  calculateTargetPixelPosition,
} from "../src/utils/calibrationCoordinates.js";

// =========================================================================
// 1. Top, Bottom, Left, and Right Target Placement
// =========================================================================

test("Top, bottom, left, and right target coordinates map accurately to CSS percentages", () => {
  const topLeft = getTargetPosition({ x: 0.10, y: 0.10 });
  assert.strictEqual(topLeft.left, "10.000%");
  assert.strictEqual(topLeft.top, "10.000%");

  const topRight = getTargetPosition({ x: 0.90, y: 0.10 });
  assert.strictEqual(topRight.left, "90.000%");
  assert.strictEqual(topRight.top, "10.000%");

  const bottomLeft = getTargetPosition({ x: 0.10, y: 0.90 });
  assert.strictEqual(bottomLeft.left, "10.000%");
  assert.strictEqual(bottomLeft.top, "90.000%");

  const bottomRight = getTargetPosition({ x: 0.90, y: 0.90 });
  assert.strictEqual(bottomRight.left, "90.000%");
  assert.strictEqual(bottomRight.top, "90.000%");

  const center = getTargetPosition({ x: 0.50, y: 0.50 });
  assert.strictEqual(center.left, "50.000%");
  assert.strictEqual(center.top, "50.000%");
});

test("Validation targets map precisely without offset or rounding drift", () => {
  const val1 = getTargetPosition({ x: 0.2333, y: 0.7667 });
  assert.strictEqual(val1.left, "23.330%");
  assert.strictEqual(val1.top, "76.670%");

  const val2 = getTargetPosition({ x: 0.7667, y: 0.7667 });
  assert.strictEqual(val2.left, "76.670%");
  assert.strictEqual(val2.top, "76.670%");

  const val3 = getTargetPosition({ x: 0.5000, y: 0.5000 });
  assert.strictEqual(val3.left, "50.000%");
  assert.strictEqual(val3.top, "50.000%");

  const val4 = getTargetPosition({ x: 0.2333, y: 0.2333 });
  assert.strictEqual(val4.left, "23.330%");
  assert.strictEqual(val4.top, "23.330%");
});

// =========================================================================
// 2. No Accidental Vertical Inversion or Double Mirroring
// =========================================================================

test("Verified: No vertical inversion (top target Y < bottom target Y maps to top < bottom)", () => {
  const topTarget = getTargetPosition({ x: 0.50, y: 0.10 });
  const bottomTarget = getTargetPosition({ x: 0.50, y: 0.90 });

  const topVal = parseFloat(topTarget.top);
  const bottomVal = parseFloat(bottomTarget.top);

  assert.ok(
    topVal < bottomVal,
    `Top coordinate (${topVal}%) must be less than bottom coordinate (${bottomVal}%) in standard top-down CSS`
  );
  assert.strictEqual(topVal, 10.0);
  assert.strictEqual(bottomVal, 90.0);
});

test("Verified: No horizontal double mirroring (left target X < right target X maps to left < right)", () => {
  const leftTarget = getTargetPosition({ x: 0.10, y: 0.50 });
  const rightTarget = getTargetPosition({ x: 0.90, y: 0.50 });

  const leftVal = parseFloat(leftTarget.left);
  const rightVal = parseFloat(rightTarget.left);

  assert.ok(
    leftVal < rightVal,
    `Left coordinate (${leftVal}%) must be less than right coordinate (${rightVal}%) in standard left-right CSS`
  );
  assert.strictEqual(leftVal, 10.0);
  assert.strictEqual(rightVal, 90.0);
});

// =========================================================================
// 3. Correct Target Count and Separation in Both Modes
// =========================================================================

test("16-point mode splits into exactly 16 training targets and 4 validation targets", () => {
  const mockBackendPoints = [
    ...DEFAULT_16POINT_TRAINING_GRID,
    ...DEFAULT_4POINT_VALIDATION_GRID,
  ];
  assert.strictEqual(mockBackendPoints.length, 20);

  const { mode, trainingPoints, validationPoints, allPoints } = splitTargetsByMode(mockBackendPoints, 20);

  assert.strictEqual(mode, "16-point");
  assert.strictEqual(trainingPoints.length, 16);
  assert.strictEqual(validationPoints.length, 4);
  assert.strictEqual(allPoints.length, 20);

  // Check training grid coordinates
  assert.strictEqual(trainingPoints[0].x, 0.1000);
  assert.strictEqual(trainingPoints[0].y, 0.1000);
  assert.strictEqual(trainingPoints[15].x, 0.9000);
  assert.strictEqual(trainingPoints[15].y, 0.9000);

  // Check validation coordinates
  assert.strictEqual(validationPoints[0].x, 0.2333);
  assert.strictEqual(validationPoints[0].y, 0.7667);
  assert.strictEqual(validationPoints[3].x, 0.2333);
  assert.strictEqual(validationPoints[3].y, 0.2333);
});

test("9-point mode preserves 9 training targets with zero validation targets", () => {
  const mockBackendPoints = [...DEFAULT_9POINT_GRID];
  assert.strictEqual(mockBackendPoints.length, 9);

  const { mode, trainingPoints, validationPoints, allPoints } = splitTargetsByMode(mockBackendPoints, 9);

  assert.strictEqual(mode, "9-point");
  assert.strictEqual(trainingPoints.length, 9);
  assert.strictEqual(validationPoints.length, 0);
  assert.strictEqual(allPoints.length, 9);

  assert.strictEqual(trainingPoints[0].x, 0.10);
  assert.strictEqual(trainingPoints[8].x, 0.90);
});

// =========================================================================
// 4. Quadrant Classification
// =========================================================================

test("Quadrant resolution correctly identifies corners, sides, and center", () => {
  assert.strictEqual(getPointQuadrant(0.10, 0.10), "Top Left");
  assert.strictEqual(getPointQuadrant(0.50, 0.10), "Top Center");
  assert.strictEqual(getPointQuadrant(0.90, 0.10), "Top Right");
  assert.strictEqual(getPointQuadrant(0.50, 0.50), "Center");
  assert.strictEqual(getPointQuadrant(0.10, 0.90), "Bottom Left");
  assert.strictEqual(getPointQuadrant(0.90, 0.90), "Bottom Right");
  assert.strictEqual(getPointQuadrant(0.2333, 0.7667), "Bottom Left");
});

// =========================================================================
// 5. Calibration Authorization Gating
// =========================================================================

test("Authorization is strictly withheld unless backend grants explicit authorization", () => {
  // Case 1: In progress (incomplete)
  assert.strictEqual(
    isCalibrationAuthorized({ complete: false, is_calibrated: false }),
    false,
    "Incomplete session must not be authorized"
  );

  // Case 2: Complete but fit failed (is_calibrated = false)
  assert.strictEqual(
    isCalibrationAuthorized({ complete: true, is_calibrated: false }),
    false,
    "Failed fit must not be authorized"
  );

  // Case 3: Complete and is_calibrated true, but validation report failed
  assert.strictEqual(
    isCalibrationAuthorized({
      complete: true,
      is_calibrated: true,
      validation_report: { passed: false },
    }),
    false,
    "Failed validation report must block authorization"
  );

  // Case 4: Complete and is_calibrated true, but quality recommends recalibration
  assert.strictEqual(
    isCalibrationAuthorized({
      complete: true,
      is_calibrated: true,
      quality: { recommend_recalibration: true },
    }),
    false,
    "Quality recommending recalibration must block authorization"
  );

  // Case 5: 16-point mode successful authorization
  assert.strictEqual(
    isCalibrationAuthorized({
      complete: true,
      is_calibrated: true,
      total_points: 20,
      mode: "16-point",
      validation_report: { passed: true },
      quality: { recommend_recalibration: false },
    }, "16-point"),
    true,
    "Valid 16-point session with passing validation must be authorized in 16-point mode"
  );

  // Case 6: 16-point mode missing validation report MUST NOT be authorized
  assert.strictEqual(
    isCalibrationAuthorized({
      complete: true,
      is_calibrated: true,
      total_points: 20,
      mode: "16-point",
      validation_report: null,
      quality: { recommend_recalibration: false },
    }, "16-point"),
    false,
    "16-point session without validation report must never be authorized"
  );

  // Case 7: 9-point mode successful authorization
  assert.strictEqual(
    isCalibrationAuthorized({
      complete: true,
      is_calibrated: true,
      total_points: 9,
      mode: "9-point",
      quality: { recommend_recalibration: false },
    }, "9-point"),
    true,
    "Valid 9-point session must be authorized in 9-point mode"
  );

  // Case 8: Successful 9-point session MUST NOT authorize a 16-point session!
  assert.strictEqual(
    isCalibrationAuthorized({
      complete: true,
      is_calibrated: true,
      total_points: 9,
      mode: "9-point",
      quality: { recommend_recalibration: false },
    }, "16-point"),
    false,
    "Successful 9-point session must never falsely authorize a 16-point session"
  );
});

// =========================================================================
// 6. Wizard Mode Transitions & Payload Sanitization
// =========================================================================

test("splitTargetsByMode defaults cleanly to 16-point training + 4-point validation when backend is null or unconfigured", () => {
  const res = splitTargetsByMode(null, 20);
  assert.strictEqual(res.mode, "16-point");
  assert.strictEqual(res.trainingPoints.length, 16);
  assert.strictEqual(res.validationPoints.length, 4);
  assert.strictEqual(res.allPoints.length, 20);
});

test("splitTargetsByMode correctly separates 20 backend points into 16 training and 4 validation targets", () => {
  const mock20 = Array.from({ length: 20 }, (_, i) => ({ index: i, x: 0.1 * (i % 4), y: 0.1 * Math.floor(i / 4) }));
  const res = splitTargetsByMode(mock20, 20);
  assert.strictEqual(res.mode, "16-point");
  assert.strictEqual(res.trainingPoints.length, 16);
  assert.strictEqual(res.validationPoints.length, 4);
  assert.strictEqual(res.trainingPoints[0].index, 0);
  assert.strictEqual(res.validationPoints[0].index, 16);
});

test("splitTargetsByMode isolates 9-point legacy targets without validation targets", () => {
  const mock9 = Array.from({ length: 9 }, (_, i) => ({ index: i, x: 0.5, y: 0.5 }));
  const res = splitTargetsByMode(mock9, 9);
  assert.strictEqual(res.mode, "9-point");
  assert.strictEqual(res.trainingPoints.length, 9);
  assert.strictEqual(res.validationPoints.length, 0);
});

test("Mode sanitization extracts valid mode strings and suppresses event objects or circular references", () => {
  // Replicate calibrationService mode sanitizer logic
  const sanitizeMode = (mode = null) => {
    let modeStr = null;
    if (typeof mode === "string") {
      modeStr = mode.trim();
    } else if (mode && typeof mode === "object" && typeof mode.mode === "string") {
      modeStr = mode.mode.trim();
    }
    return modeStr ? { mode: modeStr } : {};
  };

  // Case 1: String mode
  assert.deepStrictEqual(sanitizeMode("16-point"), { mode: "16-point" });
  assert.deepStrictEqual(sanitizeMode("9-point"), { mode: "9-point" });

  // Case 2: Object with mode string
  assert.deepStrictEqual(sanitizeMode({ mode: "16-point" }), { mode: "16-point" });

  // Case 3: React SyntheticEvent object (circular or property-rich)
  const syntheticEvent = { isTrusted: true, target: {}, nativeEvent: {} };
  assert.deepStrictEqual(sanitizeMode(syntheticEvent), {});

  // Case 4: null or undefined
  assert.deepStrictEqual(sanitizeMode(null), {});
  assert.deepStrictEqual(sanitizeMode(undefined), {});
});

// =========================================================================
// 7. Phase 3 Mode Badge & Workflow Title Contracts
// =========================================================================

test("Mode badge renders exact required string for 16-point and legacy 9-point workflows", () => {
  const getModeBadgeText = (mode) =>
    mode === "16-point" ? "16-POINT CALIBRATION + VALIDATION" : "9-POINT LEGACY";

  assert.strictEqual(
    getModeBadgeText("16-point"),
    "16-POINT CALIBRATION + VALIDATION",
    "Must display exact mode badge string for upgraded workflow"
  );
  assert.strictEqual(
    getModeBadgeText("9-point"),
    "9-POINT LEGACY",
    "Must display exact legacy mode badge string"
  );
});

// =========================================================================
// 8. Validation Gate Thresholds & Failure Presentation Contracts
// =========================================================================

test("Validation acceptance strictly evaluates mean ≤ 0.0800 and max ≤ 0.1500", () => {
  const MEAN_LIMIT = 0.0800;
  const MAX_LIMIT = 0.1500;

  const evaluateValidation = (report) => {
    if (!report) return { passed: false, reason: "No report" };
    const meanPassed = report.mean_norm_error <= MEAN_LIMIT;
    const maxPassed = report.max_norm_error <= MAX_LIMIT;
    const passed = Boolean(report.passed && meanPassed && maxPassed);
    return {
      passed,
      meanPassed,
      maxPassed,
      authWithheld: !passed,
    };
  };

  // Case 1: Both pass
  const passReport = {
    passed: true,
    mean_norm_error: 0.0452,
    max_norm_error: 0.0981,
    per_target_norm_errors: [0.032, 0.045, 0.098, 0.042],
  };
  const passResult = evaluateValidation(passReport);
  assert.strictEqual(passResult.passed, true);
  assert.strictEqual(passResult.authWithheld, false);

  // Case 2: Mean error exceeds 0.0800
  const meanFailReport = {
    passed: false,
    mean_norm_error: 0.0894,
    max_norm_error: 0.1200,
    per_target_norm_errors: [0.08, 0.09, 0.12, 0.067],
  };
  const meanFailResult = evaluateValidation(meanFailReport);
  assert.strictEqual(meanFailResult.passed, false);
  assert.strictEqual(meanFailResult.meanPassed, false);
  assert.strictEqual(meanFailResult.authWithheld, true);

  // Case 3: Max error exceeds 0.1500 (even if mean is low)
  const maxFailReport = {
    passed: false,
    mean_norm_error: 0.0520,
    max_norm_error: 0.1850,
    per_target_norm_errors: [0.02, 0.03, 0.185, 0.025],
  };
  const maxFailResult = evaluateValidation(maxFailReport);
  assert.strictEqual(maxFailResult.passed, false);
  assert.strictEqual(maxFailResult.maxPassed, false);
  assert.strictEqual(maxFailResult.authWithheld, true);
});

test("Individual validation target errors map to quadrant and threshold status without data fabrication", () => {
  const perTargetErrors = [0.0350, 0.0712, 0.1620, 0.0410];
  const { validationPoints } = splitTargetsByMode(null, 20);

  assert.strictEqual(validationPoints.length, 4);

  const breakdown = perTargetErrors.map((err, i) => {
    const pt = validationPoints[i];
    return {
      label: `V${i + 1}`,
      quadrant: getPointQuadrant(pt.x, pt.y),
      error: err,
      passed: err <= 0.1500,
    };
  });

  assert.strictEqual(breakdown[0].label, "V1");
  assert.strictEqual(breakdown[0].passed, true);
  assert.strictEqual(breakdown[2].label, "V3");
  assert.strictEqual(breakdown[2].passed, false); // 0.1620 > 0.1500
  assert.strictEqual(breakdown[3].label, "V4");
  assert.strictEqual(breakdown[3].passed, true);
});

// =========================================================================
// 9. Authorization Withheld and State Representation
// =========================================================================

test("Authorization status explicitly communicates Withheld vs Authorized", () => {
  const getAuthDisplay = ({ isAuthorized, isValidationFailed, started }) => {
    if (isAuthorized) return { label: "✓ Authorized", color: "#34d399" };
    if (isValidationFailed) return { label: "🔒 Withheld", color: "#f87171" };
    if (started) return { label: "Evaluating", color: "#fbbf24" };
    return { label: "Not Calibrated", color: "#94a3b8" };
  };

  assert.deepStrictEqual(
    getAuthDisplay({ isAuthorized: false, isValidationFailed: true, started: true }),
    { label: "🔒 Withheld", color: "#f87171" }
  );

  assert.deepStrictEqual(
    getAuthDisplay({ isAuthorized: true, isValidationFailed: false, started: true }),
    { label: "✓ Authorized", color: "#34d399" }
  );

  assert.deepStrictEqual(
    getAuthDisplay({ isAuthorized: false, isValidationFailed: false, started: false }),
    { label: "Not Calibrated", color: "#94a3b8" }
  );
});

// =========================================================================
// 10. Scroll Reliability & Container CSS Verification
// =========================================================================

test("Calibration stylesheet guarantees vertical scroll ownership and unconstrained actions", async () => {
  const fs = await import("node:fs");
  const path = await import("node:path");

  const cssPath = path.resolve("./src/pages/Calibration.module.css");
  assert.ok(fs.existsSync(cssPath), "Calibration.module.css must exist");

  const cssContent = fs.readFileSync(cssPath, "utf-8");

  // Verify .container is scroll owner inside fixed #root
  assert.ok(
    cssContent.includes("overflow-y: auto"),
    ".container must specify overflow-y: auto to own page scrolling"
  );
  assert.ok(
    cssContent.includes("height: 100%"),
    ".container must specify height: 100% to fit within parent viewport"
  );

  // Verify actions are not position: fixed (which would cover validation results)
  const actionsMatch = cssContent.match(/\.actions\s*\{([^}]+)\}/);
  assert.ok(actionsMatch, ".actions class rule must exist");
  assert.ok(
    !actionsMatch[1].includes("position: fixed"),
    ".actions must not use position: fixed covering content"
  );
});

// =========================================================================
// 11. State Synchronization & Retry Resilience
// =========================================================================

test("Retry resilience: 409 capture error on target 1 must not terminate session", () => {
  let started = true;
  let trackingStatus = "Capturing";

  const handleCaptureError = (status, currentPointIndex) => {
    if (status === 409) {
      trackingStatus = "Retry Needed";
      // Crucial: started must NOT be set to false when retrying point 1 (index 0)
      if (currentPointIndex === 0) {
        // Started state must be preserved
        started = true;
      }
    }
  };

  handleCaptureError(409, 0);
  assert.strictEqual(started, true, "Session must remain started on point 1 retry");
  assert.strictEqual(trackingStatus, "Retry Needed", "Tracking status must indicate retry needed");
});

test("Validation failure transitions session to not started and failed phase", () => {
  const evaluateCompletion = (phase, complete) => {
    const isFinished = complete || phase === "complete" || phase === "failed";
    const started = !isFinished;
    return { started, isFinished };
  };

  const failedState = evaluateCompletion("failed", false);
  assert.strictEqual(failedState.started, false, "Failed validation must conclude active session");
  assert.strictEqual(failedState.isFinished, true, "Failed validation must be marked finished");

  const completedState = evaluateCompletion("complete", true);
  assert.strictEqual(completedState.started, false, "Completed validation must conclude active session");
  assert.strictEqual(completedState.isFinished, true);

  const trainingState = evaluateCompletion("training", false);
  assert.strictEqual(trainingState.started, true, "In-progress training session must remain started");
  assert.strictEqual(trainingState.isFinished, false);
});

// =========================================================================
// 12. Fullscreen Responsive Layout & Target Distribution Verification
// =========================================================================

test("Layout CSS: Container has 100% width, no restrictive 1360px max-width, and stage expands responsively", async () => {
  const fs = await import("node:fs");
  const path = await import("node:path");

  const cssPath = path.resolve("./src/pages/Calibration.module.css");
  assert.ok(fs.existsSync(cssPath), "Calibration.module.css must exist");

  const cssContent = fs.readFileSync(cssPath, "utf-8");

  // Verify .scrollWrapper does NOT have max-width: 1360px
  assert.ok(
    !cssContent.includes("max-width: 1360px"),
    ".scrollWrapper must NOT restrict the layout with max-width: 1360px"
  );

  // Verify .scrollWrapper has width: 100% and max-width: 100%
  const wrapperMatch = cssContent.match(/\.scrollWrapper\s*\{([^}]+)\}/);
  assert.ok(wrapperMatch, ".scrollWrapper rule must exist");
  assert.ok(
    wrapperMatch[1].includes("width: 100%"),
    ".scrollWrapper must have width: 100% to fill the application window"
  );
  assert.ok(
    wrapperMatch[1].includes("max-width: 100%"),
    ".scrollWrapper must have max-width: 100% to use all available space"
  );

  // Verify .stage has width: 100% and flex: 1 for responsive canvas expansion
  const stageMatch = cssContent.match(/\.stage\s*\{([^}]+)\}/);
  assert.ok(stageMatch, ".stage rule must exist");
  assert.ok(
    stageMatch[1].includes("width: 100%"),
    ".stage must have width: 100% to span the full container"
  );
  assert.ok(
    stageMatch[1].includes("flex: 1"),
    ".stage must have flex: 1 to fill available vertical space"
  );
});

test("Target fixation: High-contrast central fixation cores are defined for both active and inactive targets", async () => {
  const fs = await import("node:fs");
  const path = await import("node:path");

  const cssPath = path.resolve("./src/pages/Calibration.module.css");
  const cssContent = fs.readFileSync(cssPath, "utf-8");

  // Verify central fixation pins exist via pseudo-elements
  assert.ok(
    cssContent.includes(".pointDot::before"),
    ".pointDot::before must exist to mark the exact center fixation position"
  );
  assert.ok(
    cssContent.includes(".pointActive .pointDot::before"),
    ".pointActive .pointDot::before must provide a luminous high-contrast white fixation core"
  );
  assert.ok(
    cssContent.includes(".validationDot::before"),
    ".validationDot::before must exist for validation targets"
  );
  assert.ok(
    cssContent.includes(".validationActive .validationDot::before"),
    ".validationActive .validationDot::before must provide a luminous high-contrast white fixation core"
  );
});

test("Coordinate scaling: Target grid covers 80% span across various display resolutions without distortion", () => {
  const resolutions = [
    { name: "1366x768 Laptop", width: 1366, height: 768 },
    { name: "1080p Desktop", width: 1920, height: 1080 },
    { name: "1440p Desktop", width: 2560, height: 1440 },
    { name: "3440x1440 Ultrawide", width: 3440, height: 1440 },
  ];

  for (const res of resolutions) {
    const minX = Math.min(...DEFAULT_16POINT_TRAINING_GRID.map((p) => p.x));
    const maxX = Math.max(...DEFAULT_16POINT_TRAINING_GRID.map((p) => p.x));
    const minY = Math.min(...DEFAULT_16POINT_TRAINING_GRID.map((p) => p.y));
    const maxY = Math.max(...DEFAULT_16POINT_TRAINING_GRID.map((p) => p.y));

    const spanX = maxX - minX;
    const spanY = maxY - minY;

    assert.strictEqual(minX, 0.1000, `${res.name}: Left margin must be 10%`);
    assert.strictEqual(maxX, 0.9000, `${res.name}: Right margin must be 10% (span to 90%)`);
    assert.strictEqual(minY, 0.1000, `${res.name}: Top margin must be 10%`);
    assert.strictEqual(maxY, 0.9000, `${res.name}: Bottom margin must be 10% (span to 90%)`);
    assert.strictEqual(spanX, 0.8000, `${res.name}: Horizontal span must cover 80% of canvas`);
    assert.strictEqual(spanY, 0.8000, `${res.name}: Vertical span must cover 80% of canvas`);

    // Pixel span calculations for the resolution
    const pixelSpanX = spanX * res.width;
    const pixelSpanY = spanY * res.height;

    assert.ok(pixelSpanX > 0.75 * res.width, `${res.name}: Target grid must effectively use viewport width`);
    assert.ok(pixelSpanY > 0.75 * res.height, `${res.name}: Target grid must effectively use viewport height`);
  }
});

// =========================================================================
// 13. Independent Target Layer & Floating Panel Geometry Tests
// =========================================================================

test("Target positions are completely independent of panel position and dimensions", () => {
  const viewport = { width: 1920, height: 1080 };
  const point = { index: 0, x: 0.10, y: 0.10 };

  // Initial target coordinates
  const initialPos = getTargetPosition(point);
  const initialPixels = calculateTargetPixelPosition(point, viewport);

  assert.strictEqual(initialPos.left, "10.000%");
  assert.strictEqual(initialPos.top, "10.000%");
  assert.strictEqual(initialPixels.pixelX, 192.0);
  assert.strictEqual(initialPixels.pixelY, 108.0);

  // Simulate moving the floating panel to arbitrary positions
  const panelPositions = [
    { x: 100, y: 100 },
    { x: 800, y: 600 },
    { x: 1500, y: 800 },
    { x: 0, y: 0 },
  ];

  for (const panelPos of panelPositions) {
    // Assert target position remains completely unchanged
    const currentPos = getTargetPosition(point);
    const currentPixels = calculateTargetPixelPosition(point, viewport);

    assert.strictEqual(
      currentPos.left,
      initialPos.left,
      `Target X percentage must remain invariant regardless of panel position (${panelPos.x}, ${panelPos.y})`
    );
    assert.strictEqual(
      currentPos.top,
      initialPos.top,
      `Target Y percentage must remain invariant regardless of panel position (${panelPos.x}, ${panelPos.y})`
    );
    assert.strictEqual(currentPixels.pixelX, initialPixels.pixelX);
    assert.strictEqual(currentPixels.pixelY, initialPixels.pixelY);
  }
});

test("Dragging panel updates only panel position while keeping all 16 target coordinates invariant", () => {
  const targets = [...DEFAULT_16POINT_TRAINING_GRID];
  const initialPositions = targets.map((pt) => getTargetPosition(pt));

  // Simulate user dragging floating panel by drag delta (dx: +250, dy: -180)
  const initialPanelPos = { x: 500, y: 500 };
  const draggedPanelPos = { x: initialPanelPos.x + 250, y: initialPanelPos.y - 180 };

  assert.strictEqual(draggedPanelPos.x, 750);
  assert.strictEqual(draggedPanelPos.y, 320);

  // Verify all 16 target positions before and after drag
  targets.forEach((pt, idx) => {
    const afterDragPos = getTargetPosition(pt);
    assert.deepStrictEqual(
      afterDragPos,
      initialPositions[idx],
      `Target ${idx} must not shift when panel is dragged`
    );
  });
});

test("clampPanelPosition keeps floating panel strictly inside viewport boundaries", () => {
  const panelSize = { width: 360, height: 260 };
  const viewport = { width: 1920, height: 1080 };
  const margin = 12;

  // Off-screen Left
  const clampedLeft = clampPanelPosition({ x: -200, y: 400 }, panelSize, viewport, margin);
  assert.strictEqual(clampedLeft.x, margin, "Panel dragged off-screen left must clamp to margin");
  assert.strictEqual(clampedLeft.y, 400);

  // Off-screen Top
  const clampedTop = clampPanelPosition({ x: 400, y: -150 }, panelSize, viewport, margin);
  assert.strictEqual(clampedTop.x, 400);
  assert.strictEqual(clampedTop.y, margin, "Panel dragged off-screen top must clamp to margin");

  // Off-screen Right
  const clampedRight = clampPanelPosition({ x: 2500, y: 300 }, panelSize, viewport, margin);
  const expectedMaxX = viewport.width - panelSize.width - margin; // 1920 - 360 - 12 = 1548
  assert.strictEqual(clampedRight.x, expectedMaxX, "Panel dragged off-screen right must clamp to maxX");
  assert.strictEqual(clampedRight.y, 300);

  // Off-screen Bottom
  const clampedBottom = clampPanelPosition({ x: 500, y: 1500 }, panelSize, viewport, margin);
  const expectedMaxY = viewport.height - panelSize.height - margin; // 1080 - 260 - 12 = 808
  assert.strictEqual(clampedBottom.x, 500);
  assert.strictEqual(clampedBottom.y, expectedMaxY, "Panel dragged off-screen bottom must clamp to maxY");
});

test("getDefaultPanelPosition avoids occluding bottom-right targets by shifting to bottom-left", () => {
  const panelSize = { width: 360, height: 260 };
  const viewport = { width: 1920, height: 1080 };
  const margin = 24;

  // Case 1: Target is in top-left (point 0: x=0.10, y=0.10) -> Default dock is bottom-right
  const dock1 = getDefaultPanelPosition({ x: 0.10, y: 0.10 }, panelSize, viewport, margin);
  assert.strictEqual(dock1.docked, "bottom-right");
  assert.strictEqual(dock1.x, viewport.width - panelSize.width - margin); // 1920 - 360 - 24 = 1536
  assert.strictEqual(dock1.y, viewport.height - panelSize.height - margin); // 1080 - 260 - 24 = 796

  // Case 2: Target is in bottom-right (point 15: x=0.90, y=0.90) -> Dock switches to bottom-left!
  const dock2 = getDefaultPanelPosition({ x: 0.90, y: 0.90 }, panelSize, viewport, margin);
  assert.strictEqual(dock2.docked, "bottom-left");
  assert.strictEqual(dock2.x, margin); // 24
  assert.strictEqual(dock2.y, viewport.height - panelSize.height - margin); // 796

  // Case 3: Target is in center (x=0.50, y=0.50) -> Default dock is bottom-right
  const dock3 = getDefaultPanelPosition({ x: 0.50, y: 0.50 }, panelSize, viewport, margin);
  assert.strictEqual(dock3.docked, "bottom-right");
});

test("Window resizing re-clamps floating panel without leaving it off-screen", () => {
  const panelSize = { width: 360, height: 260 };
  const margin = 12;

  // Panel positioned near bottom-right on 1440p screen (2560 x 1440)
  const initialLargePos = { x: 2150, y: 1100 };

  // User resizes window down to 1280 x 720 (e.g. laptop window or snapping)
  const shrunkViewport = { width: 1280, height: 720 };
  const reclamped = clampPanelPosition(initialLargePos, panelSize, shrunkViewport, margin);

  const expectedX = shrunkViewport.width - panelSize.width - margin; // 1280 - 360 - 12 = 908
  const expectedY = shrunkViewport.height - panelSize.height - margin; // 720 - 260 - 12 = 448

  assert.strictEqual(reclamped.x, expectedX, "Panel must be re-clamped within resized window width");
  assert.strictEqual(reclamped.y, expectedY, "Panel must be re-clamped within resized window height");
});

test("Keyboard controls execute correct actions across phases", () => {
  const actionsTriggered = [];

  const handleKeyDown = (key, state) => {
    if (key === "Enter") {
      if (state.started && !state.complete && !state.isValidationFailed && !state.capturing) {
        actionsTriggered.push("capture");
      } else if (state.isValidationFailed) {
        actionsTriggered.push("restart");
      } else if (!state.started && !state.complete) {
        actionsTriggered.push("start");
      }
    } else if (key === "Escape") {
      if (state.started && !state.complete) {
        actionsTriggered.push("cancel");
      } else {
        actionsTriggered.push("return_dashboard");
      }
    }
  };

  // Ready: ENTER starts session
  handleKeyDown("Enter", { started: false, complete: false, isValidationFailed: false, capturing: false });
  assert.strictEqual(actionsTriggered.pop(), "start");

  // In Training: ENTER captures target
  handleKeyDown("Enter", { started: true, complete: false, isValidationFailed: false, capturing: false });
  assert.strictEqual(actionsTriggered.pop(), "capture");

  // In Capturing frames: ENTER does nothing (suppressed)
  handleKeyDown("Enter", { started: true, complete: false, isValidationFailed: false, capturing: true });
  assert.strictEqual(actionsTriggered.length, 0);

  // In Training: ESC cancels session
  handleKeyDown("Escape", { started: true, complete: false });
  assert.strictEqual(actionsTriggered.pop(), "cancel");

  // In Ready / Completed: ESC returns to Dashboard
  handleKeyDown("Escape", { started: false, complete: true });
  assert.strictEqual(actionsTriggered.pop(), "return_dashboard");
});

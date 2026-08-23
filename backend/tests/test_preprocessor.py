"""Unit tests for Sprint 4 Audio Preprocessor layer (AGC & Peak Limiter filters)."""

from __future__ import annotations

import numpy as np

from backend.voice.preprocessor import (
    AdaptiveGainControlFilter,
    AudioPreprocessor,
    PeakLimiterFilter,
)
from backend.voice.recognizer import VoiceRecognitionConfig, VoiceRecognitionService


def test_agc_scaling_on_quiet_audio():
    agc = AdaptiveGainControlFilter(target_rms=0.04, min_gain=1.0, max_gain=40.0, enabled=True)
    # Generate quiet signal (RMS ~0.002)
    rng = np.random.default_rng(42)
    quiet_samples = rng.normal(0, 0.002, 16000).astype(np.float32)

    initial_rms = float(np.sqrt(np.mean(np.square(quiet_samples))))
    processed = agc.process(quiet_samples)
    final_rms = float(np.sqrt(np.mean(np.square(processed))))

    assert initial_rms < 0.005
    # Gain should scale RMS up toward target (0.04) up to max_gain (20x boost)
    assert final_rms > initial_rms * 10.0
    assert abs(final_rms - 0.04) < 0.01


def test_agc_gain_clamping():
    agc = AdaptiveGainControlFilter(target_rms=0.04, min_gain=1.0, max_gain=5.0, enabled=True)
    # Quiet audio (RMS 0.002)
    samples = (np.ones(16000, dtype=np.float32) * 0.002)
    processed = agc.process(samples)

    # Gain target would be 0.04 / 0.002 = 20x, but max_gain is 5.0x
    expected_peak = 0.002 * 5.0
    assert abs(float(np.max(np.abs(processed))) - expected_peak) < 1e-5


def test_agc_silence_bypass():
    agc = AdaptiveGainControlFilter(target_rms=0.04, enabled=True)
    zeros = np.zeros(16000, dtype=np.float32)
    processed = agc.process(zeros)
    np.testing.assert_array_equal(processed, zeros)


def test_agc_disabled_toggle():
    agc = AdaptiveGainControlFilter(target_rms=0.04, enabled=False)
    samples = np.ones(16000, dtype=np.float32) * 0.002
    processed = agc.process(samples)
    np.testing.assert_array_equal(processed, samples)


def test_peak_limiter_clamping():
    limiter = PeakLimiterFilter(threshold=1.0, enabled=True)
    loud_samples = np.array([-2.5, -0.5, 0.0, 0.8, 1.8], dtype=np.float32)
    processed = limiter.process(loud_samples)
    expected = np.array([-1.0, -0.5, 0.0, 0.8, 1.0], dtype=np.float32)
    np.testing.assert_array_almost_equal(processed, expected)


def test_peak_limiter_disabled_toggle():
    limiter = PeakLimiterFilter(threshold=1.0, enabled=False)
    loud_samples = np.array([-2.5, 1.8], dtype=np.float32)
    processed = limiter.process(loud_samples)
    np.testing.assert_array_equal(processed, loud_samples)


def test_audio_preprocessor_pipeline_composition():
    preprocessor = AudioPreprocessor(
        filters=[
            AdaptiveGainControlFilter(target_rms=0.04, max_gain=40.0, enabled=True),
            PeakLimiterFilter(threshold=1.0, enabled=True),
        ],
        enabled=True,
    )
    quiet_samples = (np.ones(16000, dtype=np.float32) * 0.001)
    processed = preprocessor.process(quiet_samples)

    # RMS scaled up and all samples strictly <= 1.0
    assert float(np.max(np.abs(processed))) <= 1.0
    assert float(np.sqrt(np.mean(np.square(processed)))) > 0.01


def test_audio_preprocessor_disabled_pipeline():
    preprocessor = AudioPreprocessor(enabled=False)
    quiet_samples = (np.ones(16000, dtype=np.float32) * 0.001)
    processed = preprocessor.process(quiet_samples)
    np.testing.assert_array_equal(processed, quiet_samples)


def test_recognizer_preprocessor_injection():
    custom_preprocessor = AudioPreprocessor(
        filters=[PeakLimiterFilter(threshold=0.5, enabled=True)],
        enabled=True,
    )
    cfg = VoiceRecognitionConfig(preprocessor=custom_preprocessor)
    service = VoiceRecognitionService(config=cfg)

    loud_samples = np.array([2.0, -2.0], dtype=np.float32)
    processed = service._preprocess_audio(loud_samples)
    expected = np.array([0.5, -0.5], dtype=np.float32)
    np.testing.assert_array_almost_equal(processed, expected)

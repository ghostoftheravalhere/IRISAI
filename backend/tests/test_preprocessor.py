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


# ==============================================================================
# Comprehensive Phase 5 Verification Tests (STT Audio Pipeline Tuning)
# ==============================================================================


def test_empty_audio_handling():
    """Requirement 1: Verify empty audio is safely handled across all filters and recognizer."""
    empty = np.array([], dtype=np.float32)
    agc = AdaptiveGainControlFilter()
    limiter = PeakLimiterFilter()
    preprocessor = AudioPreprocessor()
    service = VoiceRecognitionService()

    assert agc.process(empty).size == 0
    assert limiter.process(empty).size == 0
    assert preprocessor.process(empty).size == 0
    assert service._preprocess_audio(empty).size == 0
    assert agc.process(empty).dtype == np.float32
    assert service._preprocess_audio(empty).dtype == np.float32


def test_silence_and_near_silence_not_amplified():
    """Requirement 2: Silent and near-silent input does not become amplified noise."""
    agc = AdaptiveGainControlFilter(target_rms=0.04, min_gain=0.5, max_gain=8.0, silence_threshold=1e-4)
    service = VoiceRecognitionService()

    zeros = np.zeros(16000, dtype=np.float32)
    out_zeros = agc.process(zeros)
    np.testing.assert_array_equal(out_zeros, zeros)

    # Sub-threshold room noise (RMS < 1e-4)
    near_silence = np.full(16000, 5e-5, dtype=np.float32)
    out_near_silence = service._preprocess_audio(near_silence)
    # Must NOT be amplified to peak 0.90 or boosted by AGC
    assert float(np.max(np.abs(out_near_silence))) < 1e-3


def test_quiet_speech_like_audio_amplification():
    """Requirement 3: Quiet speech is amplified up toward target RMS bounded by max_gain."""
    agc = AdaptiveGainControlFilter(target_rms=0.04, min_gain=0.5, max_gain=8.0, peak_limit=0.95)
    # Quiet speech-like audio (RMS ~0.005)
    t = np.linspace(0, 1.0, 16000, endpoint=False)
    quiet_signal = (0.007 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)

    initial_rms = float(np.sqrt(np.mean(np.square(quiet_signal))))
    processed = agc.process(quiet_signal)
    final_rms = float(np.sqrt(np.mean(np.square(processed))))

    assert initial_rms < 0.01
    # 0.04 / ~0.005 = ~8.0x gain boost
    assert final_rms > initial_rms * 4.0
    assert abs(final_rms - 0.04) < 0.01
    assert float(np.max(np.abs(processed))) <= 0.95


def test_normal_level_audio_preservation():
    """Requirement 4: Normal speech audio dynamics are preserved with unity gain."""
    agc = AdaptiveGainControlFilter(target_rms=0.04, min_gain=0.5, max_gain=8.0, peak_limit=0.95)
    t = np.linspace(0, 1.0, 16000, endpoint=False)
    normal_signal = (0.0565 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)  # RMS ~0.040

    initial_rms = float(np.sqrt(np.mean(np.square(normal_signal))))
    processed = agc.process(normal_signal)
    final_rms = float(np.sqrt(np.mean(np.square(processed))))

    assert abs(initial_rms - 0.040) < 0.002
    assert abs(final_rms - 0.040) < 0.002
    # Preserves waveform without distortion
    np.testing.assert_allclose(processed, normal_signal, rtol=1e-2, atol=1e-3)


def test_loud_audio_attenuation():
    """Requirement 5: Loud audio is safely attenuated down toward target RMS."""
    agc = AdaptiveGainControlFilter(target_rms=0.04, min_gain=0.5, max_gain=8.0, peak_limit=0.95)
    t = np.linspace(0, 1.0, 16000, endpoint=False)
    loud_signal = (0.15 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)  # RMS ~0.106

    initial_rms = float(np.sqrt(np.mean(np.square(loud_signal))))
    processed = agc.process(loud_signal)
    final_rms = float(np.sqrt(np.mean(np.square(processed))))

    # Gain should attenuate: min_gain = 0.5 allows down to 0.5x
    assert final_rms < initial_rms
    assert final_rms <= initial_rms * 0.55
    assert float(np.max(np.abs(processed))) <= 0.95


def test_peaks_close_to_digital_limit_headroom_safety():
    """Requirement 6: Plosives or peaks close to digital limit constrain AGC gain."""
    agc = AdaptiveGainControlFilter(target_rms=0.04, min_gain=0.5, max_gain=8.0, peak_limit=0.95)
    # Signal with RMS 0.02 (which would ask for 2.0x gain), but a sharp peak at 0.80
    samples = np.full(16000, 0.02, dtype=np.float32)
    samples[500] = 0.80  # plosive transient

    processed = agc.process(samples)
    out_peak = float(np.max(np.abs(processed)))

    # Without peak awareness, 2.0x * 0.80 = 1.60 (hard clipping!).
    # With peak awareness, gain is constrained to 0.95 / 0.80 = ~1.1875x.
    assert out_peak <= 0.95 + 1e-5
    # The non-peak samples are scaled by the peak-safe gain
    assert processed[0] < 0.03


def test_output_dtype_range_and_finite_safety():
    """Requirement 7: Output remains strictly finite float32 within [-peak_limit, +peak_limit] even with NaN/Inf."""
    service = VoiceRecognitionService()
    dirty_input = np.array([np.nan, np.inf, -np.inf, 2.5, -3.0, 0.5], dtype=np.float32)

    processed = service._preprocess_audio(dirty_input)
    assert processed.dtype == np.float32
    assert np.all(np.isfinite(processed))
    assert float(np.max(processed)) <= 0.95
    assert float(np.min(processed)) >= -0.95


def test_stereo_channel_selection_picks_louder_capsule():
    """Requirement 8: Stereo channel selection picks the louder capsule avoiding phase cancellation."""
    # Channel 0: quiet, Channel 1: loud speech
    t = np.linspace(0, 1.0, 4000, endpoint=False)
    ch0 = (0.01 * np.sin(2 * np.pi * 400 * t)).astype(np.float32)
    ch1 = (0.08 * np.sin(2 * np.pi * 400 * t)).astype(np.float32)
    stereo_block = np.column_stack([ch0, ch1])

    selected = VoiceRecognitionService.select_audio_channel(stereo_block)
    np.testing.assert_array_equal(selected, ch1)

    # Reverse: Channel 0 loud, Channel 1 quiet
    stereo_block_rev = np.column_stack([ch1, ch0])
    selected_rev = VoiceRecognitionService.select_audio_channel(stereo_block_rev)
    np.testing.assert_array_equal(selected_rev, ch1)

    # Mono input passthrough
    mono_1d = ch1.reshape(-1)
    np.testing.assert_array_equal(VoiceRecognitionService.select_audio_channel(mono_1d), mono_1d)


def test_transcription_segment_rejection_behavior():
    """Requirement 9: Transcription filtering rejects empty, punctuation, and low-confidence segments."""
    from types import SimpleNamespace

    service = VoiceRecognitionService(
        config=VoiceRecognitionConfig(no_speech_threshold=0.80, logprob_threshold=-1.0)
    )

    # 1. Empty text -> Rejected
    assert service.is_segment_valid(SimpleNamespace(text="", no_speech_prob=0.1, avg_logprob=-0.2)) is False

    # 2. Punctuation only -> Rejected
    assert service.is_segment_valid(SimpleNamespace(text="...", no_speech_prob=0.1, avg_logprob=-0.2)) is False
    assert service.is_segment_valid(SimpleNamespace(text=" . ", no_speech_prob=0.1, avg_logprob=-0.2)) is False

    # 3. Low-confidence noise (both no_speech >= 0.80 AND avg_logprob < -1.0) -> Rejected
    assert service.is_segment_valid(SimpleNamespace(text="click", no_speech_prob=0.85, avg_logprob=-1.4)) is False

    # 4. Short command with high no_speech_prob BUT high token logprob (confidence) -> KEPT!
    assert service.is_segment_valid(SimpleNamespace(text="click", no_speech_prob=0.82, avg_logprob=-0.35)) is True

    # 5. Clear confident command -> KEPT!
    assert service.is_segment_valid(SimpleNamespace(text="open chrome", no_speech_prob=0.05, avg_logprob=-0.15)) is True


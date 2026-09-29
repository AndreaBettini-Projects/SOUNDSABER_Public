#pragma once

#include <Arduino.h>
#include <cstdint>

// =========================================================================
// SHARED AUDIO CONSTANTS
// =========================================================================
constexpr int AUDIO_SAMPLE_RATE   = 16000;  // 16 kHz PCM Audio
constexpr int AUDIO_TARGET_LENGTH = 24000;  // 1.5 Seconds of audio (16000 * 1.5)

// =========================================================================
// FUNCTION DECLARATIONS (EXPORTED TO .INO)
// =========================================================================

// Initializes ArduTFLite and verifies tensor memory allocation
bool initialize_audio_ml();

// Returns a pointer to the 48 KB shared audio buffer inside audio_dsp.cpp
int16_t* get_shared_audio_buffer();

// Intermediate DSP steps
void preprocess_and_normalize_audio(const int16_t* raw_audio);
void compute_mel_spectrogram(const int16_t* raw_audio);
void compute_deltas();

// Executes full feature extraction + TFLite inference and returns predicted class name
String process_audio_and_run_cnn(const int16_t* raw_mic_buffer);
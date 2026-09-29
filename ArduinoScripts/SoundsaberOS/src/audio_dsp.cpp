#include "audio_dsp.h"
#include "model_data.h"
#include <ArduTFLite.h>
#include <math.h>
#include <cmath>
#include <cstdint>
#include <arduinoFFT.h>
#include "mel_filterbank.h"
#include "config.h"

// to avoid index overflow
inline int clamp_index(int value, int min_val, int max_val) {
    if (value < min_val) return min_val;
    if (value > max_val) return max_val;
    return value;
}

// namespace is used to prevent symbol collisions with other parts of the codebase 
namespace {
    // constants same as the Python training script
    constexpr int N_MELS               = 64; // check that N_MELS, NUM_FRAMES and NUM_CHANNELS match the model input shape [64, 43, 3]
    constexpr int NUM_FRAMES           = 43;
    constexpr int NUM_CHANNELS         = 3;
    constexpr int N_FFT                = 2048; 
    constexpr int HOP_LENGTH           = 512;
    constexpr int SEARCH_RADIUS    = 4;
    constexpr float DELTA1_DIVISOR = 60.0f;   
    constexpr float DELTA2_DIVISOR = 462.0f;  // check Librosa definitions to derive these last 3 values

    const int kTensorArenaSize = 100000; // obtained from TensorArena_estimation.py
    alignas(8)uint8_t tensor_arena[kTensorArenaSize];

    int16_t sample_buffer[AUDIO_TARGET_LENGTH]; // see audio_dsp.h for AUDIO_TARGET_LENGTH definition

    // OPTIMIZED SCRATCHPAD (27 KB Total - fits comfortably in Nano BLE 33 RAM)
    struct DSP_Scratch {
        float fft_real[N_FFT];                      // 8 KB
        float fft_imag[N_FFT];                      // 8 KB
        float mel_spectrogram[N_MELS][NUM_FRAMES]; // 11 KB
    };
    static DSP_Scratch scratch;
    #define fft_real_buffer    scratch.fft_real
    #define fft_imag_buffer    scratch.fft_imag
    #define mel_buffer         scratch.mel_spectrogram

    // Mean/Std scaling parameters from Python training (UPDATE THIS HARDCODED PART! Use Calculate_mean_std.py)
    const float MEAN_CHANNELS[3] = { -44.7909f, 0.08148f, -0.006638f };
    const float STD_CHANNELS[3]  = {  16.1832f, 2.1165f,   1.0876f   };

    // Biquad HP filter coefficients for 3-stage SOS filter (cutoff ~ 50 Hz, fs=16kHz)
    struct BiquadCoeffs {
        float b0, b1, b2;
        float a1, a2;
    };
    const BiquadCoeffs SOS_SECTIONS[3] = {
        {0.968728731f, -0.968728731f, 0.0f, -0.980555319f, 0.0f},
        {1.0f,         -2.0f,         1.0f, -1.968349240f, 0.968728731f},
        {1.0f,         -2.0f,         1.0f, -1.987555693f, 0.987938887f}
    };
} // namespace

extern TfLiteTensor* tflInputTensor;
extern TfLiteTensor* tflOutputTensor;

bool initialize_audio_ml() {
    Serial.println("\n================ TENSOR DIAGNOSTICS ================");
    Serial.println("Initializing TFLite Model via ArduTFLite...");

    if (!modelInit(my_cnn_model_tflite, tensor_arena, kTensorArenaSize)) {
        Serial.println("❌ Model Initialization Failed!");
        return false;
    }

    Serial.println("✅ TFLite Model Loaded Successfully!");

    if (tflInputTensor && tflOutputTensor) {
        Serial.println("--- INPUT TENSOR ---");
        Serial.print("  Raw Bytes      : "); Serial.println(tflInputTensor->bytes);
        Serial.print("  Float Capacity : "); Serial.println(tflInputTensor->bytes / sizeof(float));
        Serial.print("  Target Needed  : "); Serial.println(N_MELS * NUM_FRAMES * NUM_CHANNELS);

        Serial.println("--- OUTPUT TENSOR ---");
        Serial.print("  Raw Bytes      : "); Serial.println(tflOutputTensor->bytes);
        Serial.print("  Float Capacity : "); Serial.println(tflOutputTensor->bytes / sizeof(float));
    } else {
        Serial.println("❌ Error: Tensor pointers are NULL!");
        return false;
    }
    Serial.println("====================================================\n");

    return true;
}

// ============================================================================
// DSP ALGORITHMS
// ============================================================================

void preprocess_and_normalize_audio(const int16_t* raw_audio) {
    int16_t* audio_ptr = const_cast<int16_t*>(raw_audio);
    float w1[3] = {0.0f, 0.0f, 0.0f};
    float w2[3] = {0.0f, 0.0f, 0.0f};
    float max_peak = 1e-6f;

    // PASS 1: 3-stage SOS High-Pass Filter in-place on int16_t buffer
    for (int i = 0; i < AUDIO_TARGET_LENGTH; i++) {
        float sample = static_cast<float>(audio_ptr[i]) / 32768.0f;

        for (int s = 0; s < 3; s++) {
            float w0 = sample - SOS_SECTIONS[s].a1 * w1[s] - SOS_SECTIONS[s].a2 * w2[s];
            sample = SOS_SECTIONS[s].b0 * w0 + SOS_SECTIONS[s].b1 * w1[s] + SOS_SECTIONS[s].b2 * w2[s];
            w2[s] = w1[s];
            w1[s] = w0;
        }

        // Clip and save back in-place
        if (sample > 1.0f) sample = 1.0f;
        if (sample < -1.0f) sample = -1.0f;
        audio_ptr[i] = static_cast<int16_t>(sample * 32767.0f);

        float abs_s = std::abs(sample);
        if (abs_s > max_peak) max_peak = abs_s;
    }
}

void compute_mel_spectrogram(const int16_t* raw_audio) {
    ArduinoFFT<float> FFT(fft_real_buffer, fft_imag_buffer, N_FFT, (float)AUDIO_SAMPLE_RATE);

    // 1. Loop over time frames
    for (int f = 0; f < NUM_FRAMES; f++) {
        int start_idx = f * HOP_LENGTH;

        // Load raw audio scaled to [-1.0, 1.0] and apply EXPLICIT Periodic Hann Window
        for (int i = 0; i < N_FFT; i++) {
            int idx = start_idx + i;
            float sample = (idx < AUDIO_TARGET_LENGTH) ? (static_cast<float>(raw_audio[idx]) / 32768.0f) : 0.0f;
            
            // Periodic Hann window formula matching Librosa (fftbins=True)
            float hann_window = 0.5f * (1.0f - std::cos(2.0f * static_cast<float>(M_PI) * static_cast<float>(i) / static_cast<float>(N_FFT)));
            
            fft_real_buffer[i] = sample * hann_window;
            fft_imag_buffer[i] = 0.0f;
        }

        // FFT computation (windowing already applied manually above)
        FFT.compute(FFT_FORWARD);

        // Calculate power spectrum magnitude squared
        for (int k = 0; k < (N_FFT / 2 + 1); k++) {
            float re = fft_real_buffer[k], im = fft_imag_buffer[k];
            fft_real_buffer[k] = (re * re) + (im * im);
        }

        // Apply Mel Filterbank
        for (int m = 0; m < N_MELS; m++) {
            float power = 0.0f;
            for (int k = 0; k < (N_FFT / 2 + 1); k++) {
                power += MEL_FILTERS[m][k] * fft_real_buffer[k];
            }
            mel_buffer[m][f] = power;
        }
    }

    // 2. Convert Power to dB (matches librosa.power_to_db with ref=np.max)
    float global_max = 1e-10f;
    for (int m = 0; m < N_MELS; m++) {
        for (int f = 0; f < NUM_FRAMES; f++) {
            if (mel_buffer[m][f] > global_max) {
                global_max = mel_buffer[m][f];
            }
        }
    }

    for (int m = 0; m < N_MELS; m++) {
        for (int f = 0; f < NUM_FRAMES; f++) {
            float db = 10.0f * std::log10((mel_buffer[m][f] + 1e-10f) / global_max);
            mel_buffer[m][f] = (db < -80.0f) ? -80.0f : db;
        }
    }
}

void compute_deltas() {
    int flat_idx = 0;
    for (int m = 0; m < N_MELS; m++) {
        for (int f = 0; f < NUM_FRAMES; f++) {
            
            float ch0 = mel_buffer[m][f];
            float d1_sum = 0.0f;
            float d2_sum = 0.0f;

            for (int offset = -SEARCH_RADIUS; offset <= SEARCH_RADIUS; offset++) {
                int time_idx = clamp_index(f + offset, 0, NUM_FRAMES - 1);
                float log_mel_value = mel_buffer[m][time_idx];

                d1_sum += static_cast<float>(offset) * log_mel_value;
                d2_sum += (3.0f * static_cast<float>(offset * offset) - 20.0f) * log_mel_value;
            }

            float ch1 = d1_sum / DELTA1_DIVISOR;
            float ch2 = d2_sum / DELTA2_DIVISOR;

            // Normalize channels and write directly into TFLite input tensor [64][43][3]
            modelSetInput((ch0 - MEAN_CHANNELS[0]) / (STD_CHANNELS[0] + 1e-8f), flat_idx++);
            modelSetInput((ch1 - MEAN_CHANNELS[1]) / (STD_CHANNELS[1] + 1e-8f), flat_idx++);
            modelSetInput((ch2 - MEAN_CHANNELS[2]) / (STD_CHANNELS[2] + 1e-8f), flat_idx++);
        }
    }
}


String process_audio_and_run_cnn(const int16_t* raw_mic_buffer) {

    // ============ INSTANTANEOUS TRANSIENT / CLAP GATE ==================
    for (int i = 0; i < AUDIO_TARGET_LENGTH; i++) {
        // If a single sample crosses a loud peak threshold (e.g., 22,000 out of 32,767),
        // treat it as a sharp clap, pop, or physical tap and reject it immediately.
        if (std::abs(raw_mic_buffer[i]) > MAX_CEILING) {
            return "Unknown"; 
        }
    }
    // ============ UPPER CEILING CLIPPING / TOUCH DETECTOR ==================
    int consecutive_ceiling_hits = 0;
    int max_consecutive_hits = 0;
    
    for (int i = 0; i < AUDIO_TARGET_LENGTH; i++) {
        // Check if sample keeps hitting near the absolute max rail (e.g., > 20000 out of 32767)
        if (std::abs(raw_mic_buffer[i]) > 0.8 * MAX_CEILING) {
            consecutive_ceiling_hits++;
            if (consecutive_ceiling_hits > max_consecutive_hits) {
                max_consecutive_hits = consecutive_ceiling_hits;
            }
        } else {
            consecutive_ceiling_hits = 0;
        }
    }
    
    // If the signal stays pinned/clipping at the ceiling for more than ~50 consecutive samples,
    // it's mechanical touching/friction, not voice.
    if (max_consecutive_hits > 50) {
        return "Unknown";
    }
    // =======================================================================

    // 1. Compute Base Mel Spectrogram (includes possible preprocess step)
    preprocess_and_normalize_audio(raw_mic_buffer);
    compute_mel_spectrogram(raw_mic_buffer);

    // 2. Compute Deltas & Populate TFLite input tensor
    compute_deltas();

    // 3. Run Neural Network Inference
    if (!modelRunInference()) {
        Serial.println("❌ Inference Failed!"); // if it fails, could be the tensor arena size is too small
        return "Unknown";
    }

    // 4. Read Output Class Probabilities
    float p_soundsaber = modelGetOutput(0);
    float p_mutation   = modelGetOutput(1);
    float p_darkness   = modelGetOutput(2);
    float p_unknown    = modelGetOutput(3);

    // DEBUG PRINT RAW OUTPUTS
    Serial.println("--- MODEL OUTPUT PROBABILITIES ---");
    Serial.print("Soundsaber : "); Serial.println(p_soundsaber, 4);
    Serial.print("Mutation   : "); Serial.println(p_mutation, 4);
    Serial.print("Darkness   : "); Serial.println(p_darkness, 4);
    Serial.print("Unknown    : "); Serial.println(p_unknown, 4);
    Serial.println("----------------------------------");

    // 5. Classification Decision Logic
    constexpr float CONFIDENCE_THRESHOLD = 0.85f; // HARD-CODED THRESHOLD (see Pictures/CM_ideal.png threshold)

    if (p_soundsaber >= CONFIDENCE_THRESHOLD) return "Soundsaber";
    if (p_mutation   >= CONFIDENCE_THRESHOLD) return "Mutation";
    if (p_darkness   >= CONFIDENCE_THRESHOLD) return "Darkness";

    return "Unknown";
}

int16_t* get_shared_audio_buffer() {
    return sample_buffer;
}
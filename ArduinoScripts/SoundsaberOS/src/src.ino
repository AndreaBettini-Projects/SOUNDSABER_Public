#include <PDM.h> // Arduino microphone lib
#include "audio_dsp.h"
#include "imu.h"
#include "config.h"

// State machine states (see config.h)
SystemState current_system_state = STATE_SLEEPING;
SystemState prev_system_state = STATE_SLEEPING;
PerformanceState current_performance_state = STATE_IDLE;
PerformanceState prev_performance_state = STATE_IDLE;

int16_t* target_audio_buffer = nullptr;
int16_t pdm_rx_buffer[512];
volatile int samples_read = 0;
int total_samples_collected = 0;

// Helper functions to make serial send characters, not numbers, to avoid confusion
const char* systemStateName(SystemState state) {
    switch (state) {
        case STATE_SLEEPING: return "SLEEP";
        case STATE_RECORDING: return "RECORD";
        default: return "UNKNOWN";
    }
}

const char* performanceStateName(PerformanceState state) {
    switch (state) {
        case STATE_IDLE: return "IDLE";
        case STATE_JEDI: return "JEDI";
        case STATE_SITH: return "SITH";
        default: return "UNKNOWN";
    }
}

// Circular Pre-Roll Buffer to store past audio
int16_t pre_roll_buffer[PRE_ROLL_SAMPLES];
int pre_roll_head = 0;

void onPDMdata() {
    int bytesAvailable = PDM.available();
    PDM.read(pdm_rx_buffer, bytesAvailable);
    samples_read = bytesAvailable / 2;
}

void setup() {
    Serial.begin(1000000);
    while (!Serial && millis() < 4000);

    Serial.println("\n==================================================");
    Serial.println("  Arduino Nano 33 BLE - Voice Keyword Spotter");
    Serial.println("==================================================");

    initIMU(); // Initialize the BMI270/BMM150 IMU and Madgwick filter + calibration

    if (!initialize_audio_ml()) {
        Serial.println("❌ Model initialization failed!");
        while (1);
    }

    target_audio_buffer = get_shared_audio_buffer();

    PDM.onReceive(onPDMdata);
    if (!PDM.begin(1, AUDIO_SAMPLE_RATE)) {
        Serial.println("❌ Failed to start PDM Microphone!");
        while (1);
    }
    PDM.setGain(MIC_GAIN);

    // 1. Clear pre-roll memory
    memset(pre_roll_buffer, 0, sizeof(pre_roll_buffer));

    // 2. Flush PDM power-on spike
    delay(500);
    samples_read = 0;

    // 3. Prime the pre-roll buffer with 0.6s of ambient room noise
    // Serial.print("⏳ Priming pre-roll audio buffer...");
    unsigned long start_prime = millis();
    while (millis() - start_prime < 600) {
        if (samples_read > 0) {
            int count = samples_read;
            samples_read = 0;
            for (int i = 0; i < count; i++) {
                pre_roll_buffer[pre_roll_head] = pdm_rx_buffer[i];
                pre_roll_head = (pre_roll_head + 1) % PRE_ROLL_SAMPLES;
            }
        }
    }

    Serial.println(" Ready.");
    Serial.print("💤 Status: SLEEPING (Listening for sound peak > ");
    Serial.print(VOICE_THRESHOLD);
    Serial.println(")\n");

    // Explicitly report startup state so GUI and board are synchronized
    Serial.print("SS:");
    Serial.println(systemStateName(current_system_state));
    Serial.print("PS:");
    Serial.println(performanceStateName(current_performance_state));
}

void loop() {

    // // ==================== PRINT VOLUME PEAKS==========================
    // // Used only to find voice and noise optimal threshold values
    // int16_t* mic_buffer = get_shared_audio_buffer(); 
    // float max_sample = 0.0f;
    // for (int i = 0; i < AUDIO_TARGET_LENGTH; i++) {
    //     int16_t val = mic_buffer[i];
    //     float abs_val = static_cast<float>(val < 0 ? -val : val);
    //     if (abs_val > max_sample) {
    //         max_sample = abs_val;
    //     }
    // }
    // if (max_sample > 0.0f) {
    //     Serial.print("Peak: ");
    //     Serial.println(max_sample, 0);
    // }
    // // ================================================================


    static String keyword = "Unknown";
    bool new_inference_ready = false;

    // Run IMU if in background even if no performance
    saber_commands();

    if (samples_read <= 0) return;

    int count = samples_read;
    samples_read = 0;

    // 1. Measure peak volume
    int16_t current_peak = 0;
    for (int i = 0; i < count; i++) {
        int16_t abs_val = abs(pdm_rx_buffer[i]);
        if (abs_val > current_peak) current_peak = abs_val;
    }

    switch (current_system_state) {
        case STATE_SLEEPING:
            for (int i = 0; i < count; i++) {
                pre_roll_buffer[pre_roll_head] = pdm_rx_buffer[i];
                pre_roll_head = (pre_roll_head + 1) % PRE_ROLL_SAMPLES;
            }

            if (current_peak >= VOICE_THRESHOLD) {
                total_samples_collected = 0;
                int read_pos = pre_roll_head;
                for (int i = 0; i < PRE_ROLL_SAMPLES; i++) {
                    target_audio_buffer[total_samples_collected++] = pre_roll_buffer[read_pos];
                    read_pos = (read_pos + 1) % PRE_ROLL_SAMPLES;
                }

                for (int i = 0; i < count && total_samples_collected < AUDIO_TARGET_LENGTH; i++) {
                    target_audio_buffer[total_samples_collected++] = pdm_rx_buffer[i];
                }

                current_system_state = STATE_RECORDING;
            }
            break;

        case STATE_RECORDING:
            for (int i = 0; i < count; i++) {
                if (total_samples_collected < AUDIO_TARGET_LENGTH)
                    target_audio_buffer[total_samples_collected++] = pdm_rx_buffer[i];
            }

            if (total_samples_collected >= AUDIO_TARGET_LENGTH) {
                keyword = process_audio_and_run_cnn(target_audio_buffer);
                keyword.trim();
                if (keyword != "Unknown") {new_inference_ready = true;}
                Serial.print("[CNN] Detected keyword: <");
                Serial.print(keyword);
                Serial.println(">");

                current_system_state = STATE_SLEEPING;
                total_samples_collected = 0;
            }
            break;
    }

    // Performance State Machine (Only update on fresh keyword events)
    if (new_inference_ready) {
        PerformanceState old_state = current_performance_state;

        if (keyword.equalsIgnoreCase("Darkness")) {
            current_performance_state = STATE_IDLE;
        }
        else if (current_performance_state == STATE_IDLE && keyword.equalsIgnoreCase("Soundsaber")) {
            current_performance_state = STATE_JEDI;
            resetIMUFilter();
        }
        else if (keyword.equalsIgnoreCase("Mutation")) {
            if (current_performance_state == STATE_JEDI) {
                current_performance_state = STATE_SITH;
            }
            else if (current_performance_state == STATE_SITH) {
                current_performance_state = STATE_JEDI;
                resetIMUFilter();
            }
        }

        // Debug state transition
        if (current_performance_state != old_state) {
            Serial.print("[STATE] Performance: ");
            Serial.print(performanceStateName(old_state));
            Serial.print(" -> ");
            Serial.println(performanceStateName(current_performance_state));
        }
        else {
            Serial.print("[STATE] Performance unchanged: ");
            Serial.println(performanceStateName(current_performance_state));
        }
    }

    if (current_system_state != prev_system_state) {
        Serial.print("SS:");
        Serial.println(systemStateName(current_system_state));
        prev_system_state = current_system_state;
    }

    if (current_performance_state != prev_performance_state) {
        Serial.print("PS:");
        Serial.println(performanceStateName(current_performance_state));
        prev_performance_state = current_performance_state;
    }
}
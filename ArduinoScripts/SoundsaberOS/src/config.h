#ifndef CONFIG_H
#define CONFIG_H

// --- Audio & ML Parameters ---
#define VOICE_THRESHOLD 10000 // good for a silent room, can be increased for louder environments
#define MAX_CEILING 22000 // if volume ceiling is hit for many cycles it assumes noise and skips inference (max 32767)
#define MIC_GAIN        80 // Never change this value, it was used during training
constexpr int PRE_ROLL_SAMPLES = 8800; // Pre-roll centers the keyword in the 1.5s buffer

// State machine states
enum SystemState {STATE_SLEEPING, STATE_RECORDING};
enum PerformanceState {STATE_IDLE, STATE_JEDI, STATE_SITH};
extern SystemState current_system_state;
extern PerformanceState current_performance_state;


// --- IMU & Motion Tracking Parameters (runtime editable with IMU_serialcom.py) --- (extern means they are defined elsewhere)
extern float LIN_THRESH;  // Variance thresholds for ZUPT (does not enter FX mode if linear acc is below this)
extern float THRUST_DEADBAND; // (measured in g) if linmag<g-band or linmag>g+band that means there is linear acceleration, not only gravity

extern float SMOOTHING_FACTOR; // Adjust: higher = snappier, lower = smoother
extern unsigned long PRINT_INTERVAL_MS; // IMU output data interval to be sent to audio engine
extern unsigned long LOCKOUT_TIME; // Lockout time in milliseconds to prevent rapid FX switching
extern unsigned long CYCLES_REQUIRED; // Number of cycles to confirm a dominant direction for FX activation
extern float FLICK_THRESHOLD; // degrees/sec where boost kicks in
extern float BOOST_COEFF; // flick boost strength
extern float BLEEDER_RATE; // bleeder to center yaw back gradually

constexpr float IMU_SAMPLE_RATE = 99.84f; // see Arduino accelerometer datasheet
constexpr float BETA = 0.1; // Magdwick feedback factor. The higher, the faster but less accurate correction.


#endif
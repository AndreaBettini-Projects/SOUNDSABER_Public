#include <Arduino.h>
#include <Arduino_BMI270_BMM150.h>
#include <MadgwickAHRS.h>
#include "imu.h"
#include "config.h"
#include <NanoBLEFlashPrefs.h>


// ========================= CALIBRATION (set True if needed) ====================================

// Consider deleting all the magnetometer calibration, 
// since it's not useful (yaw drift not an issue after gyro calibration)

#define RUN_MAG_CALIBRATION false
#define RUN_GYRO_CALIBRATION true
struct MagCalibration {
    float biasX;
    float biasY;
    float biasZ;
};

MagCalibration magCalibration;
float magBiasX = 0.0f;
float magBiasY = 0.0f;
float magBiasZ = 0.0f;
static bool magValid = false; // better check since magnetometer is very slow

float gyroBiasX = 0;
float gyroBiasY = 0;
float gyroBiasZ = 0;

NanoBLEFlashPrefs flashPrefs;

void calibrateMagnetometer() {

    Serial.println();
    Serial.println("==============================");
    Serial.println(" MAGNETOMETER CALIBRATION");
    Serial.println("==============================");
    Serial.println();
    Serial.println("Rotate and tilt the device");
    Serial.println("through as many orientations");
    Serial.println("as possible for 30 seconds.");
    Serial.println();

    float minX =  10000.0f; // just to initialize to a high value so it's sure the new min will be lower
    float maxX = -10000.0f; // same but max

    float minY =  10000.0f;
    float maxY = -10000.0f;

    float minZ =  10000.0f;
    float maxZ = -10000.0f;

    unsigned long startTime = millis();
    unsigned long lastPrint = 0;

    while (millis() - startTime < 30000) {

        if (IMU.magneticFieldAvailable()) {

            float mx, my, mz;

            IMU.readMagneticField(mx, my, mz);

            minX = min(minX, mx);
            maxX = max(maxX, mx);

            minY = min(minY, my);
            maxY = max(maxY, my);

            minZ = min(minZ, mz);
            maxZ = max(maxZ, mz);
        }

        if (millis() - lastPrint >= 1000) {
            lastPrint = millis();

            Serial.print("X: ");
            Serial.print(minX, 1);
            Serial.print(" .. ");
            Serial.print(maxX, 1);

            Serial.print(" | Y: ");
            Serial.print(minY, 1);
            Serial.print(" .. ");
            Serial.print(maxY, 1);

            Serial.print(" | Z: ");
            Serial.print(minZ, 1);
            Serial.print(" .. ");
            Serial.println(maxZ, 1);
        }
    }

    magBiasX = (maxX + minX) * 0.5f;
    magBiasY = (maxY + minY) * 0.5f;
    magBiasZ = (maxZ + minZ) * 0.5f;

    Serial.println();
    Serial.println("Calibration complete.");

    Serial.print("Bias X = ");
    Serial.println(magBiasX, 4);

    Serial.print("Bias Y = ");
    Serial.println(magBiasY, 4);

    Serial.print("Bias Z = ");
    Serial.println(magBiasZ, 4);

    saveMagCalibration();
}

void loadMagCalibration() {
    int rc = flashPrefs.readPrefs(
        &magCalibration,
        sizeof(magCalibration)
    );

    if (rc == 0) {
        magBiasX = magCalibration.biasX;
        magBiasY = magCalibration.biasY;
        magBiasZ = magCalibration.biasZ;

        Serial.println("Mag calibration loaded:");

        Serial.print("X: ");
        Serial.println(magBiasX, 4);

        Serial.print("Y: ");
        Serial.println(magBiasY, 4);

        Serial.print("Z: ");
        Serial.println(magBiasZ, 4);
    }
    else {
        Serial.println("No valid mag calibration found.");
        Serial.println("Using zero offsets.");
    }
}

void saveMagCalibration() {
    magCalibration.biasX = magBiasX;
    magCalibration.biasY = magBiasY;
    magCalibration.biasZ = magBiasZ;

    int rc = flashPrefs.writePrefs(
        &magCalibration,
        sizeof(magCalibration)
    );

    if (rc == 0) {
        Serial.println("Mag calibration saved to flash.");
    }
    else {
        Serial.print("ERROR saving calibration: ");
        Serial.println(flashPrefs.errorString(rc));
    }
}

void calibrateGyro()
{
    const int N = 500;

    float sx = 0;
    float sy = 0;
    float sz = 0;

    int count = 0;

    while (count < N) {
        if (IMU.gyroscopeAvailable()) {

            float gx, gy, gz;
            IMU.readGyroscope(gx, gy, gz);

            sx += gx;
            sy += gy;
            sz += gz;

            count++;
        }
    }

    gyroBiasX = sx / N;
    gyroBiasY = sy / N;
    gyroBiasZ = sz / N;
}


// ============================== RUNTIME PARAMETERS =============================================

// Default Runtime Parameters (can be updated via IMU_serialcom.py)
float LIN_THRESH = 0.4f; // does not enter FX mode if linear acceleration is not strong enough (see FX_stateMachine drawing)
float THRUST_DEADBAND = 2.0f; // (measured in g) if linmag<g-band or linmag>g+band that means there is linear acceleration, not only gravity
float SMOOTHING_FACTOR = 0.12f; // the lower, the smoother but also introduces lag
float FLICK_THRESHOLD = 100.0f; // degrees/sec where boost kicks in
float BOOST_COEFF = 0.02; // flick boost strength
float BLEEDER_RATE = 0.001f; // Slow, smooth return to yaw center
unsigned long PRINT_INTERVAL_MS = 20; // set 10 for motion control, 800 for visual inspection on serial monitor
unsigned long LOCKOUT_TIME = 500; 
unsigned long CYCLES_REQUIRED = 3; 



// Runtime parameters via serial
void processSerialCommands() {
    if (Serial.available() > 0) {
        String input = Serial.readStringUntil('\n');
        input.trim();

        if (input.startsWith("v:")) {
            LIN_THRESH = input.substring(2).toFloat();
            Serial.print("⚡ LIN_THRESH -> "); Serial.println(LIN_THRESH, 5);
        } 
        else if (input.startsWith("d:")) {
            THRUST_DEADBAND = input.substring(2).toFloat();
            Serial.print("⚡ THRUST_DEADBAND -> "); Serial.println(THRUST_DEADBAND);
        }
        else if (input.startsWith("p:")) {
            PRINT_INTERVAL_MS = input.substring(2).toInt();
            Serial.print("⚡ PRINT_INTERVAL_MS -> "); Serial.println(PRINT_INTERVAL_MS);
        }
        else if (input.startsWith("l:")) {
            LOCKOUT_TIME = input.substring(2).toInt();
            Serial.print("⚡ LOCKOUT_TIME -> "); Serial.println(LOCKOUT_TIME);
        }
        else if (input.startsWith("c:")) {
            CYCLES_REQUIRED = input.substring(2).toInt();
            Serial.print("⚡ CYCLES_REQUIRED -> "); Serial.println(CYCLES_REQUIRED);
        }
        else if (input.startsWith("f:")){
            SMOOTHING_FACTOR = input.substring(2).toFloat();
            Serial.print("⚡ SMOOTHING_FACTOR -> "); Serial.println(SMOOTHING_FACTOR);
        }
        else if (input.startsWith("b:")){
            BOOST_COEFF = input.substring(2).toFloat();
            Serial.print("⚡ BOOST_COEFF -> "); Serial.println(BOOST_COEFF);
        }
        else if (input.startsWith("t:")){
            FLICK_THRESHOLD = input.substring(2).toFloat();
            Serial.print("⚡ FLICK_THRESHOLD -> "); Serial.println(FLICK_THRESHOLD);
        }
        else if (input.startsWith("r:")){
            BLEEDER_RATE = input.substring(2).toFloat();
            Serial.print("⚡ BLEEDER_RATE -> "); Serial.println(BLEEDER_RATE);
        }
        else {
            Serial.println("❌ Unknown command.");
        }
    }
}

// ================================== VARIOUS INSTANCES ===========================================
// most of these are just brought out here to be available for printing during debugging
static float ax = 0.0f, ay = 0.0f, az = 0.0f;
static float gx = 0.0f, gy = 0.0f, gz = 0.0f;
static float mx = 0.0f, my = 0.0f, mz = 0.0f;
static float saber_yaw = 180.0f;
static float dom_x = 0.0f;
static float dom_y = 0.0f;
static float dom_z = 0.0f;

static float gravity_x = 0.0f;
static float gravity_y = 0.0f; 
static float gravity_z = 0.0f;

static float ax_linear = 0.0f;
static float ay_linear = 0.0f;
static float az_linear = 0.0f;

static float abs_x = 0.0f;
static float abs_y = 0.0f;
static float abs_z = 0.0f; // only for ease of notation

// Calculate total raw acceleration magnitude
float lin_mag = sqrt(ax_linear * ax_linear + ay_linear * ay_linear + az_linear * az_linear);


static Madgwick filter;
static unsigned long lastFilterMicros = 0;
static unsigned long lastPrintMillis = 0;
static unsigned long lastFX_time = 0; 

static bool fx_changed_flag = false; // better have a flag and print it outside the fast loop
static bool is_linear = false; 

// Static variables to hold the previous filtered states
static float smoothed_ax = 0.0f;
static float smoothed_ay = 0.0f;
static float smoothed_az = 0.0f;
// Exponential Moving Average (EMA) Filter
float smoothData(float raw, float last_smoothed, float alpha) {
    return (alpha * raw) + ((1.0f - alpha) * last_smoothed);
}



static float last_madg_yaw = 0.0f;
static bool  madg_yaw_init = false;

static float wrap180(float a) {
    while (a > 180.0f)  a -= 360.0f;
    while (a < -180.0f) a += 360.0f;
    return a;
}






static int active_fx = 0; 
static int candidate_fx = 0;
static int current_detected_fx = 0;
static int consecutive_cycles = 0;


// ====================================== FUNCTIONS ===============================================

void initIMU() {
    if (!IMU.begin()) {
        Serial.println("❌ Failed to initialize BMI270/BMM150 IMU!");
        while (1);
    }
    if (RUN_MAG_CALIBRATION) {
        calibrateMagnetometer();
    } else {
        loadMagCalibration();
    }

    if (RUN_GYRO_CALIBRATION){
        calibrateGyro();
    }

    filter.begin(IMU_SAMPLE_RATE);
    filter.setBeta(BETA);
    lastFilterMicros = micros();
    lastPrintMillis = millis();
}

void resetIMUFilter() {
    filter.begin(IMU_SAMPLE_RATE);
    filter.setBeta(BETA);
    lastFilterMicros = micros();
}

void clean_coord() {
    if (IMU.accelerationAvailable() && IMU.gyroscopeAvailable()) {
        IMU.readAcceleration(ax, ay, az);
        IMU.readGyroscope(gx, gy, gz);

        if (RUN_GYRO_CALIBRATION){
            gx -= gyroBiasX; // these are checked at every startup
            gy -= gyroBiasY;
            gz -= gyroBiasZ;
        }

        if (IMU.magneticFieldAvailable()) {
            IMU.readMagneticField(mx, my, mz);

            mx -= magBiasX;
            my -= magBiasY;
            mz -= magBiasZ;

            magValid = true;
        }
    }
}

void IMU_update() {
    // if (magValid) {
    //     filter.update(gx, gy, gz, ax, ay, az, mx, my, mz);
    // } else {
    //     filter.updateIMU(gx, gy, gz, ax, ay, az);
    // }
    filter.updateIMU(gx, gy, gz, ax, ay, az); // just using this (no magnetometer for now)
}

float yaw_boost(float current_yaw, float gz) {

        float dt = 1.0f / IMU_SAMPLE_RATE;
        float boost_multiplier = 1.0f; // default

        if (abs(gz) > FLICK_THRESHOLD) {
            // Scale up faster movements dynamically so a quick flick covers more range
            // Adjust the BOOST_COEFF multiplier to make it more or less aggressive
            boost_multiplier = 1.0f + ((abs(gz) - FLICK_THRESHOLD) * BOOST_COEFF);
            
            // Cap the maximum boost so it doesn't fly completely out of control
            if (boost_multiplier > 3.5f) {
                boost_multiplier = 3.5f;
            }
        }

        // Apply the boosted rotation to yaw
        current_yaw += gz * boost_multiplier * dt;
        return current_yaw;
}

float yaw_bleeder(float current_yaw) {
    current_yaw = (1.0f - BLEEDER_RATE) * current_yaw + (BLEEDER_RATE * 180.0f);
    // Enforce your +/- 120 degree bounds (60 to 300)
    return constrain(current_yaw, 60.0f, 300.0f);
}


void saber_commands () {
    unsigned long currentMicros = micros();

    processSerialCommands(); 
    clean_coord();
    smoothed_ax = smoothData(ax, smoothed_ax, SMOOTHING_FACTOR);
    smoothed_ay = smoothData(ay, smoothed_ay, SMOOTHING_FACTOR);
    smoothed_az = smoothData(az, smoothed_az, SMOOTHING_FACTOR);

    // High-frequency filter and integration loop
    if (currentMicros - lastFilterMicros >= (1000000.0f / IMU_SAMPLE_RATE)) {
        lastFilterMicros = currentMicros;
        
        IMU_update();

        current_detected_fx = 0; // always reset this at the beginning of HF loop

        // -----------------------------------------------------------------------------------    
        float q[4] = {filter.getQ0(), filter.getQ1(), filter.getQ2(), filter.getQ3()};
        gravity_x = 2.0f * (q[1] * q[3] - q[0] * q[2]);
        gravity_y = 2.0f * (q[0] * q[1] + q[2] * q[3]);
        gravity_z = q[0] * q[0] - q[1] * q[1] - q[2] * q[2] + q[3] * q[3];

// Test swapping the gravity components to match your chip's physical orientation:
        ax_linear = ax - gravity_x; 
        ay_linear = ay + gravity_y; // different signs depend on IMU convention
        az_linear = az - gravity_z;

        abs_x = abs(ax_linear);
        abs_y = abs(ay_linear);
        abs_z = abs(az_linear); // only for ease of notation

        // Calculate total raw acceleration magnitude
        lin_mag = sqrt((abs_x * abs_x) + (abs_y * abs_y) + (abs_z * abs_z));

        // only for debug
        // Serial.print("abs_x = ");
        // Serial.print(abs_x, 2);
        // Serial.print(", abs_y = ");
        // Serial.print(abs_y, 2);
        // Serial.print("abs_z= ");
        // Serial.println(abs_z, 2);

        // Hysteresis deadband check
        if (!is_linear) {
            // Must cross a higher threshold to trigger ON
            if (lin_mag > THRUST_DEADBAND * 1.2) {
                is_linear = true;
            }
        } else {
            // Must drop below a lower threshold to turn OFF
            if (lin_mag < THRUST_DEADBAND * 0.8) {
                is_linear = false;
            }
        }

        // -------------------------------------------------------

        // Dominant Axis FX State Machine

        dom_x = abs_x - max(abs_y, abs_z);
        dom_y = abs_y - max(abs_x, abs_z);
        dom_z = abs_z - max(abs_x, abs_y);

        if (millis() - lastFX_time > LOCKOUT_TIME) {
            if (is_linear) {
                if (dom_x > LIN_THRESH)  {
                    current_detected_fx = 1; 
                } else if (dom_y > LIN_THRESH) {
                    current_detected_fx = 2; 
                } else if (dom_z > LIN_THRESH) {
                    current_detected_fx = 3; 
                }
            }
        }

        if (current_detected_fx != 0) {
            // consecutive cycle count
            if (current_detected_fx == candidate_fx) {
                consecutive_cycles++; 
            } else {
                candidate_fx = current_detected_fx;
                consecutive_cycles = 1;
            }

            if (consecutive_cycles >= CYCLES_REQUIRED) {
                if (candidate_fx != active_fx) {
                    active_fx = candidate_fx;
                }
                else  {
                    active_fx = 0;
                }
                fx_changed_flag = true;
                lastFX_time = millis();
                consecutive_cycles = 0;
                candidate_fx = 0;
            }
        } else {
            consecutive_cycles = 0;
            candidate_fx = 0;
        }

        // Yaw from Madgwick: feed its change (as a rate) into your existing boost, then bleed
        float madg_yaw = filter.getYaw();
        if (!madg_yaw_init) { last_madg_yaw = madg_yaw; madg_yaw_init = true; }

        float dyaw = wrap180(madg_yaw - last_madg_yaw);   // deg since last update, handles 0/360 wrap
        last_madg_yaw = madg_yaw;

        float yaw_rate = dyaw * IMU_SAMPLE_RATE;          // deg/s, same units as gz
        saber_yaw = yaw_boost(saber_yaw, yaw_rate);       // unchanged function
        saber_yaw = yaw_bleeder(saber_yaw);               // unchanged function



    // ===========================================================Low-frequency print loop
    unsigned long currentMillis = millis();
    extern PerformanceState current_performance_state;

    if (current_performance_state != STATE_IDLE) { // print only if active performance
        if (currentMillis - lastPrintMillis >= PRINT_INTERVAL_MS) {
            lastPrintMillis = currentMillis;

            if (fx_changed_flag) {
                Serial.print("FX:"); 
                Serial.println(active_fx);
                fx_changed_flag = false;
            }

            Serial.print("DOM:");
            Serial.print(dom_x); Serial.print(",");
            Serial.print(dom_y); Serial.print(",");
            Serial.print(dom_z); Serial.print(",");
            Serial.println(is_linear ? 1 : 0);

            // Clamp yaw to a +/- 120 range centered around 180 (60 to 300)
            float cutoff = constrain(saber_yaw, 60.0f, 300.0f);
            cutoff = -(cutoff - 180.0f)/120.0f; // Divide by the half-span (120) to map to -1.0 to 1.0. Then invert to make clockwise positive
            // Did this only on yaw because yaw movements are uncomfortable 

            // Clamp roll (volume) and pitch (pitch) to -1,1 (max accelerometer measurement magnitude)
            float volume = constrain(-smoothed_ay, -1.0f, 1.0f);
            float pitch = constrain(smoothed_ax, -1.0f, 1.0f); // not the robotics "pitch", but the musical one

            // // Use these if you need Magdwick (must be fixed first)
            // float volume = constrain(-filter.getRoll()  / 90.0f, -1.0f, 1.0f);
            // float pitch  = constrain( filter.getPitch() / 90.0f, -1.0f, 1.0f);

            Serial.print("M:");
            // Serial.print(filter.getRoll()/180, 2); // uses Madgwick (not working atm)
            Serial.print(volume, 2); // uses raw accelerometer
            Serial.print(",");
            // Serial.print(filter.getPitch()/180, 2);// uses Madgwick (not working atm)
            Serial.print(pitch, 2);
            Serial.print(",");
            Serial.println(cutoff, 2);

            // // try sendin quaternions instead, so no gimbal lock (MUST avoid gimbal lock --> either send already bounded Euler or these and process after)
            // Serial.print("Q:");
            // Serial.print(filter.getQ0(), 4); Serial.print(",");
            // Serial.print(filter.getQ1(), 4); Serial.print(",");
            // Serial.print(filter.getQ2(), 4); Serial.print(",");
            // Serial.println(filter.getQ3(), 4);
            }
        }
    }
}
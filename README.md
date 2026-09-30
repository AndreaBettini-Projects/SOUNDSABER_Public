**SOUNDSABER** 
==============
is a spatial synthesizer with voice and motion activation. It lives and evolves in 3D space. <br>
It is a pseudo-6DoF controller, powered by an Arduino Nano and a Python-based real-time audio synthesis.

**⚠️ WORK IN PROGRESS ⚠️** - Optimizations are ongoing, check readme files

-------------------------------------------------------------------------------------------

**👁️ OVERVIEW:**
=================
**VOICE ACTIVATION** 

Based on 3 keywords:
- "Soundsaber" -- Turn ON
- "Mutation"   -- Switch Mode (synth type JEDI/SITH)
- "Darkness"   -- Turn OFF

The top-level state machine handles the Arduino operations and is found in src.ino. <br>
This state machine communicates with SaberGUI.py to turn sound on/off or switch synth type.

---------------------------------------------------------------------------------------------

The 6 Degrees of Freedom correspond to 3 axes of rotation and 3 axes for linear movements. 

**3 ROTATION CONTROLS (Knobs):**

- around X -- Volume
- around Y -- Pitch
- around Z -- Filter cutoff

Sound generation is done in audio_engine.py 

<br>

**3 LINEAR DETECTORS (FX Toggle):**

- along X -- Distorsion (FX1)
- along Y -- Reverb (FX2)
- along Z -- Chorus (FX3)

FX can be accessed through FX_engine.py

---------------------------------------------------------------------------------------------

🛠️ HARDWARE and SOFTWARE REQUIREMENTS
======================================

- Microcontroller: Arduino Nano 33 BLE Sense rev2 (ARM Cortex-M4) <br>
    with built-in sensors BMI270 (IMU) & BMM150 (Magnetometer), and onboard microphone (PDM)
- Micro-B USB cable
- Python
- Arduino IDE

--------------------------------------------------------------------------------------------

**▶️ GETTING STARTED:**
==========================


1. Install required Arduino libraries:
   - **arduinoFFT**            - FFT and spectrogram extraction for ML pipeline
   - **Arduino_BMI270_BMM150** - IMU library (use Arduino_LSM9DS1 if you are using BLE 33 Sense rev1)
   - **ArduTFLite**            - Handles the TensorFlow Lite model for keyword inference
   - **Madgwick**              - Motion control makes use of Madgwick filter for IMUs
   - **NanoBLEFlashPrefs**     - Used to access flash memory during IMU calibration

2. Install Python libraries that are required for GUI and audio engine:

   - **tkinter**
   - **serial**
   - **math**
   - **numpy**
   - **sounddevice**
   - **soundfile**

   Note that more libraries are required in order to use the ML pipeline (e.g TensorFlow). Check the ML readme.
   
4. Open src.ino in Arduino IDE, connect the Arduino board and flash the firmware. <br>

   Check your UART port name. Scripts involving serial com like Saber_GUI.py will require to specify it.
   If you need to change parameters like gains, thresholds etc. check the script-specific readme files. <br>
   You can also change keywords and use your own, recording a personal keyword dataset with the available
   scripts (Save_WAV_upd.py and RecordKeywords_upd.ino), or even modify the neural network in main_CNN.py
   at your convenience.

5. Open Saber_GUI.py and say the magic words. Enjoy!

----------------------------


**📁 REPOSITORY STRUCTURE**
=============================

<pre>
SOUNDSABER_Public
├── ArduinoScripts
│   ├── RecordKeywords
│   │   └── RecordKeywords_upd.ino
│   └── SoundsaberOS
│       └── src
│           ├── audio_dsp.cpp
│           ├── audio_dsp.h
│           ├── config.h
│           ├── imu.cpp
│           ├── imu.h
│           ├── mel_filterbank.h
│           ├── model_data.h
│           └── src.ino
├── Keywords
│   ├── dataset
│   │   ├── Original
│   │   │   ├── Darkness   -- .wav files
│   │   │   ├── Soundsaber -- .wav files
│   │   │   ├── Mutation   -- .wav files
│   │   │   └── Unknown    -- .wav files
│   │   ├── TestSet
│   │   │   ├── Darkness   -- .wav files
│   │   │   ├── Soundsaber -- .wav files
│   │   │   ├── Mutation   -- .wav files
│   │   │   └── Unknown    -- .wav files
│   │   └── TrainingSet
│   │       ├── dataset_augmented
│   │       │   ├── Darkness   -- augmented.wav files
│   │       │   ├── Soundsaber -- augmented.wav files
│   │       │   └── Mutation   -- augmented.wav files
│   │       ├── Training_Original
│   │       │   ├── Darkness   -- .wav files
│   │       │   ├── Soundsaber -- .wav files
│   │       │   ├── Mutation   -- .wav files
│   │       │   └── Unknown    -- .wav files
│   │       ├── ValidationSet
│   │       │   ├── Darkness   -- .wav files
│   │       │   ├── Soundsaber -- .wav files
│   │       │   ├── Mutation   -- .wav files
│   │       │   └── Unknown    -- .wav files
│   └── Noise
│       ├── Background_Noise  -- .wav files
│       ├── Noise_recorded    -- .wav files
│       └── RIR               -- .wav files
└── PythonScripts
    ├── ML_Pipeline
    │   ├── Audio_Data_Augmentation.py
    │   ├── Calculate_mean_std.py
    │   ├── config.py
    │   ├── Generate_String.py
    │   ├── GenerateMelSpectrogram.py
    │   ├── main_CNN.py
    │   ├── model_data.h
    │   ├── my_cnn_model.keras
    │   ├── my_cnn_model.tflite
    │   ├── Split.py
    │   ├── TensorArena_estimation.py
    │   ├── tf_lite_conversion.py
    │   └── X_train_raw.npy
    ├── RecordKeywords
    │   ├── Archive
    │   │   └── SaveWAV.py
    │   └── SaveWAV_upd.py
    └── Saber_FrontEnd
        ├── audio_engine_simple.py
        ├── audio_engine.py
        ├── FX_engine.py
        ├── piano_Aminor.wav
        ├── rhodes_Aminor.wav
        └── SaberGUI.py
  <pre>

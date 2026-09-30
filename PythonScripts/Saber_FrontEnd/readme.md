**Saber_FrontEnd** contains all the Python scripts that actually work as an interactive synthesizer.

Content: 
========

SaberGUI.py
-----------
To use Soundsaber, you only need to connect Arduino and open this one file (don't forget to specify your SERIAL_PORT at the top!)
The GUI displays in real time:

- rotation controls (your Volume, Pitch and Cutoff)
  
- synth mode (IDLE/JEDI/SITH) and FX (None/1/2/3)
  
- IMU params that can be modified on the fly to tailor the saber responsiveness (GUI shows default values)
    - LIN_THRESH [g units = 1*9.8 m/s^2] : sensitivity to linear movements to activate FXs (increase = less linear sensitivity, stronger movement required)
    - PRINT_INTERVAL [ms] : interval between IMU serial outputs that reach Saber GUI to control sound. 10ms default feels "continuous", decrease to get a "discrete-time" sound
    - CYCLES_REQUIRED : Minimum number of cycles that one linear movement (x, y or z) has to be "dominant" before the corresponding FX activates (increase = longer movements required)
    - THRUST_DEADBAND [g units] : If accelerometer raw magnitude is in 1g +- THRUST_DEADBAND, the saber assumes no linear movement (= sensitivity knob for noise rejection)
    - LOCKOUT_TIME [ms] : Timer after FX change that needs to expire to be able to change FX again to ignore recoil
    - SMOOTHING_ALPHA : Smoothing alpha coefficient for Volume and Pitch to filter out tremors (decrease to filter more)
    - BOOST_COEFF: Parameter tweak sensitivity. Boosts fast movements (increase to increase the effect)
    - FLICK_THRESHOLD [deg/s] : Minimum angular rate at which BOOST_COEFF effect is enabled
    - BLEEDER_RATE : Bleeder that keeps the cutoff tied to 50% (neutral). Increase to reset the cutoff faster, creating a fast filter decay.

- Sound parameters that can be modified on the fly to tailor your sound. To add more, change audio_engine and GUI.
    - GRAIN_DUR [s] : grain duration in JEDI granular synthesis
    - GRAIN_INT [s] : interval between grains in JEDI granular synthesis
    - GLIDE_FACTOR : portamento (glide). Decrease for slower portamento
    - RESONANCE [%] : LP/HP filter resonance
 
- Dominance plot that helps measure the desired LIN_THRESH


audio_engine.py
---------------
Defines JEDI and SITH synthesizers:
- JEDI is based on granular synthesis. Choose your source file (e.g. Rhodes_Aminor.wav) and experiment.
- SITH is a simple nasty 3-osc sawtooth.

Key parameters: 
- ALLOWED_SEMITONES : list of allowed semitones that define the key (e.g. Harmonic Minor would be [0, 2, 3, 5, 7, 8, 11])
- ROOT_FREQ [Hz] : sets the start and end values of the pitch range (e.g. 55 Hz is A1)
- sample_path : .wav source path for granular synthesis

FX_engine.py
-----------------
Defines FX1, FX2 and FX3 effects:
- FX1 is a tanh distortion
- FX2 is a comb filter reverb
- FX3 is a chorus

Feel free to change parameters like distortion drive, reverb feedback and wet/dry levels





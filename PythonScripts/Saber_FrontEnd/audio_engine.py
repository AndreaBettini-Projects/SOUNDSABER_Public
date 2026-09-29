import numpy as np
import sounddevice as sd
import soundfile as sf
from FX_engine import FXEngine


class AudioEngine:
    SAMPLE_RATE = 44100
    BLOCK_SIZE = 128
    OUTPUT_GAIN = 0.5
    sample_path = os.path.join(os.path.dirname(__file__), "PythonScripts", "Saber_FrontEnd", "rhodes_Aminor.wav")

    # Bipolar allowed semitones centered around 0 (spanning -24 to +24 semitones)
    HARMONIC_MINOR_INTERVALS = [0, 2, 3, 5, 7, 8, 11]
    ALLOWED_SEMITONES = []
    for octave in range(-2, 3):
        for interval in HARMONIC_MINOR_INTERVALS:
            sem = octave * 12 + interval
            if -24 <= sem <= 24:
                ALLOWED_SEMITONES.append(sem)

    def __init__(self, sample_path=sample_path):
        self.sample_rate = self.SAMPLE_RATE
        self.phase = 0.0
        self.current_freq = 55.0
        
        # Vibrato state variables for Sith mode
        self.vibrato_phase = 0.0
        self.last_semitone = None
        self.vibrato_time_held = 0.0

        # Tunable Sound Defaults
        self.glide_factor = 0.35
        self.volume_percent = 50.0
        self.pitch_percent = 50.0
        self.cutoff_percent = 50.0
        self.smoothed_cutoff_percent = 50.0  # to avoid flicker noise with fast cutoff transitions
        self.resonance_percent = 40.0

        self.fx = FXEngine(sample_rate=self.SAMPLE_RATE)
        self.active_fx = 0  # Track current FX state received from Arduino/GUI

        self.mode = "IDLE"
        self.is_active = False
        
        # Filter state variables for 2-pole resonant filter
        self.f_low = 0.0
        self.f_band = 0.0

        # --- LOAD SAMPLE FOR GRANULAR SYNTHESIS ---
        try:
            data, sr = sf.read(sample_path)
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
            self.jedi_sample = data.astype(np.float32)
            self.sample_len = len(self.jedi_sample)
            print(f"Loaded Sample: {sample_path} ({self.sample_len} samples)")
        except Exception as e:
            print(f"Warning: Could not load sample ({e}). Falling back to sine wave.")
            self.jedi_sample = np.sin(np.linspace(0, 2 * np.pi, 44100, dtype=np.float32))
            self.sample_len = len(self.jedi_sample)

        # Granular state variables (Defaults requested: Dur 0.5s, Interval 0.05s)
        self.grain_timer = 0
        self.active_grains = []
        self.gran_dur_sec = 0.5
        self.grain_interval_sec = 0.05

        self.stream = sd.OutputStream(
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.BLOCK_SIZE,
            callback=self._audio_callback,
        )
        self.stream.start()

    def update_sound_params(self, duration_sec, interval_sec, glide, resonance):
        self.gran_dur_sec = max(0.005, float(duration_sec))
        self.grain_interval_sec = max(0.01, float(interval_sec))
        self.glide_factor = max(0.01, min(float(glide), 1.0))
        self.resonance_percent = max(0.0, min(float(resonance), 100.0))

        print(
            f"[AUDIO] Params Updated -> "
            f"Dur: {self.gran_dur_sec}s, Interval: {self.grain_interval_sec}s, "
            f"Glide: {self.glide_factor}, Resonance: {self.resonance_percent}%"
        )

    @staticmethod
    def _clamp(value, low=0.0, high=100.0):
        return max(low, min(float(value), high))

    def _quantize_semitone(self, raw_semitones):
        """Helper method to snap any continuous semitone offset to the nearest harmonic minor note."""
        return min(self.ALLOWED_SEMITONES, key=lambda x: abs(x - raw_semitones))

    def update_state(self, state):
        state = state.upper()
        print(f"AUDIO STATE -> {state}")
        self.mode = state

        if state in ("JEDI", "SITH"):
            self.is_active = True
        else:
            self.is_active = False
            self.f_low = 0.0
            self.f_band = False
            self.active_grains.clear()
            self.last_semitone = None
            self.vibrato_time_held = 0.0

    def update_params(self, volume, frequency, cutoff):
        self.volume_percent = self._clamp(volume)
        self.pitch_percent = self._clamp(frequency)
        self.cutoff_percent = self._clamp(cutoff)

    def update_fx(self, fx_id):
        self.active_fx = int(fx_id)

    def _audio_callback(self, outdata, frames, time_info, status):
        if not self.is_active or self.mode == "IDLE":
            outdata.fill(0)
            return

        cutoff_lag = 0.05
        self.smoothed_cutoff_percent += cutoff_lag * (self.cutoff_percent - self.smoothed_cutoff_percent)
        block_output = np.zeros(frames, dtype=np.float32)

        # Bipolar Pitch Mapping: 50% pitch_percent maps to exactly 0 semitones offset
        raw_semitones = ((self.pitch_percent - 50.0) / 50.0) * 24.0

        if self.mode == "JEDI":
            # ---------------- JEDI: GRANULAR SYNTHESIS ----------------
            closest_semitone = self._quantize_semitone(raw_semitones)
            grain_speed = 2.0 ** (closest_semitone / 12.0)

            grain_len = max(32, int(self.gran_dur_sec * self.sample_rate))
            interval_samples = int(self.grain_interval_sec * self.sample_rate)
            
            self.grain_timer += frames

            if self.grain_timer >= interval_samples:
                self.grain_timer = 0
                max_start = max(1, self.sample_len - grain_len)
                start_pos = np.random.randint(0, max_start)

                self.active_grains.append({
                    "pos": float(start_pos),
                    "speed": grain_speed,
                    "length": grain_len,
                    "idx": 0,
                    "window": np.hanning(grain_len)
                })

            surviving_grains = []
            for g in self.active_grains:
                g_len = g["length"]
                g_idx_vals = np.arange(frames)
                
                sample_indices = g["pos"] + (g_idx_vals * g["speed"])
                floor_indices = np.floor(sample_indices).astype(int)
                frac = sample_indices - floor_indices
                
                valid = (floor_indices >= 0) & (floor_indices < self.sample_len - 1)
                safe_floor = np.clip(floor_indices, 0, self.sample_len - 2)
                
                s0 = self.jedi_sample[safe_floor]
                s1 = self.jedi_sample[safe_floor + 1]
                interpolated = s0 + frac * (s1 - s0)
                
                window_indices = np.clip(g["idx"] + g_idx_vals, 0, g_len - 1)
                windowed = interpolated * g["window"][window_indices]
                
                block_output[:frames] += windowed * valid
                
                g["pos"] += frames * g["speed"]
                g["idx"] += frames
                
                if g["idx"] < g_len and g["pos"] < self.sample_len:
                    surviving_grains.append(g)
            
            self.active_grains = surviving_grains
            wave = block_output

        else:
            # ---------------- SITH: CONTINUOUS OSCILLATOR WITH VIBRATO ----------------
            quantized_semitones = self._quantize_semitone(raw_semitones)
            
            # Reset vibrato fade-in timer if the quantized note changes
            if self.last_semitone != quantized_semitones:
                self.last_semitone = quantized_semitones
                self.vibrato_time_held = 0.0

            # Track time held for fade-in effect
            block_duration = frames / self.sample_rate
            self.vibrato_time_held += block_duration
            
            # Depth increases quadratically from 0 up to 5% (0.05) over 2 seconds
            max_vibrato_depth = 0.05
            fade_in_time = 2.0
            t = min(1.0, self.vibrato_time_held / fade_in_time)
            current_vibrato_depth = max_vibrato_depth * (t * t)

            # Base target frequency for the harmonic minor step
            target_freq = 55.0 * (2.0 ** (quantized_semitones / 12.0))
            self.current_freq += (target_freq - self.current_freq) * self.glide_factor

            # 7 Hz LFO generation across the block
            lfo_rate = 7.0  # Hz
            lfo_step = (lfo_rate / self.sample_rate) * 2.0 * np.pi
            lfo_phases = self.vibrato_phase + np.arange(frames) * lfo_step
            self.vibrato_phase = (self.vibrato_phase + frames * lfo_step) % (2.0 * np.pi)

            # Modulate instantaneous frequency around the center frequency by up to 5%
            lfo_val = np.sin(lfo_phases)
            instant_freqs = self.current_freq * (1.0 + current_vibrato_depth * lfo_val)

            # Sample-accurate phase accumulation for frequency modulation
            phase_steps = instant_freqs / self.sample_rate
            cumulative_steps = np.cumsum(phase_steps)
            phases = (self.phase + cumulative_steps - phase_steps) % 1.0
            self.phase = (self.phase + cumulative_steps[-1]) % 1.0

            wave1 = 2.0 * phases - 1.0
            shifted = (phases + 0.25) % 1.0
            wave2 = 2.0 * shifted - 1.0
            wave = 0.5 * wave1 + 0.5 * wave2

        # ---------------- BIPOLAR FILTER (LP / PURE / HP) ----------------
        q = 0.5 + (self.resonance_percent / 100.0) * 7.5
        damping = 1.0 / q

        if abs(self.smoothed_cutoff_percent - 50.0) < 0.5:
            filtered = wave
            self.f_low *= 0.9
            self.f_band *= 0.9
        elif self.smoothed_cutoff_percent < 50.0:
            depth = (50.0 - self.smoothed_cutoff_percent) / 50.0
            cutoff = 20.0 * (1000.0 ** (1.0 - depth))
            cutoff = max(20.0, min(cutoff, 20000.0))

            f = 2.0 * np.sin(np.pi * cutoff / self.sample_rate)
            f = min(f, 1.0)

            filtered = np.empty_like(wave)
            low = self.f_low
            band = self.f_band
            for i, sample in enumerate(wave):
                low += f * band
                high = sample - low - damping * band
                band += f * high
                filtered[i] = low
            self.f_low = low
            self.f_band = band
        else:
            depth = (self.smoothed_cutoff_percent - 50.0) / 50.0
            cutoff = 20.0 * (500.0 ** depth)
            cutoff = max(20.0, min(cutoff, 10000.0))

            f = 2.0 * np.sin(np.pi * cutoff / self.sample_rate)
            f = min(f, 1.0)

            filtered = np.empty_like(wave)
            low = self.f_low
            band = self.f_band
            for i, sample in enumerate(wave):
                low += f * band
                high = sample - low - damping * band
                band += f * high
                filtered[i] = high
            self.f_low = low
            self.f_band = band

        # ---------------- OUTPUT ----------------
        volume = self.volume_percent / 100.0

        processed_audio = self.fx.process(filtered, self.active_fx)

        outdata[:, 0] = (processed_audio * volume * self.OUTPUT_GAIN).astype(np.float32)

    def close(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
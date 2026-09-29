import numpy as np
import sounddevice as sd


class AudioEngine:
    SAMPLE_RATE = 44100
    BLOCK_SIZE = 512
    OUTPUT_GAIN = 0.2

    def __init__(self):
        self.sample_rate = self.SAMPLE_RATE
        self.phase = 0.0
        self.current_freq = 55.0
        self.glide_factor = 0.15

        self.volume_percent = 50.0
        self.pitch_percent = 50.0
        self.cutoff_percent = 50.0

        self.mode = "IDLE"
        self.is_active = False

        self.y_prev = 0.0

        self.stream = sd.OutputStream(
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.BLOCK_SIZE,
            callback=self._audio_callback,
        )
        self.stream.start()

    @staticmethod
    def _clamp(value, low=0.0, high=100.0):
        return max(low, min(float(value), high))

    def update_state(self, state):
        state = state.upper()
        print(f"AUDIO STATE -> {state}")

        if state in ("JEDI", "SITH"):
            self.mode = state
            self.is_active = True
        else:
            self.mode = "IDLE"
            self.is_active = False
            # Kill filter memory so IDLE is completely silent.
            self.y_prev = 0.0

    def update_params(self, volume, frequency, cutoff, glide=None):
        self.volume_percent = self._clamp(volume)
        self.pitch_percent = self._clamp(frequency)
        self.cutoff_percent = self._clamp(cutoff)

        if glide is not None:
            self.glide_factor = max(0.01, min(float(glide), 1.0))

    def _audio_callback(self, outdata, frames, time_info, status):
        if not self.is_active:
            outdata.fill(0)
            return

        # 0-100% -> 0-36 semitones -> 55-440 Hz
        semitone = round(self.pitch_percent * 36.0 / 100.0)
        target_freq = 55.0 * (2.0 ** (semitone / 12.0))

        self.current_freq += (
            target_freq - self.current_freq
        ) * self.glide_factor

        phase_step = self.current_freq / self.sample_rate
        phases = (
            self.phase + np.arange(frames) * phase_step
        ) % 1.0

        self.phase = (
            self.phase + frames * phase_step
        ) % 1.0

        # ---------------- WAVEFORM ----------------

        if self.mode == "SITH":
            # Dual detuned saw
            wave1 = 2.0 * phases - 1.0
            shifted = (phases + 0.25) % 1.0
            wave2 = 2.0 * shifted - 1.0
            wave = 0.5 * wave1 + 0.5 * wave2

        else:  # JEDI
            fundamental = np.sin(2.0 * np.pi * phases)
            octave = np.sin(4.0 * np.pi * phases) * 0.3
            wave = (fundamental + octave) / 1.3

        # ---------------- FILTER ----------------

        cutoff = 20.0 * (10.0 ** (3.0 * self.cutoff_percent / 100.0))
        alpha = 1.0 - np.exp(
            -2.0 * np.pi * cutoff / self.sample_rate
        )
        alpha = max(0.01, min(alpha, 1.0))

        filtered = np.empty_like(wave)

        y = self.y_prev
        for i, sample in enumerate(wave):
            y += alpha * (sample - y)
            filtered[i] = y

        self.y_prev = y

        # ---------------- OUTPUT ----------------

        volume = self.volume_percent / 100.0
        outdata[:, 0] = (
            filtered * volume * self.OUTPUT_GAIN
        ).astype(np.float32)

    def close(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
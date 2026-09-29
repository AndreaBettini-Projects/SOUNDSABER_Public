import numpy as np

class FXEngine:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        
        # --- FX2: Reverb State (Comb & Allpass feedback buffers) ---
        self.reverb_buffer_len = int(sample_rate * 0.05)  # 50ms 
        self.comb_buffer = np.zeros(self.reverb_buffer_len, dtype=np.float32)
        self.comb_index = 0

        # --- FX3: Chorus/Modulation State ---
        self.chorus_buffer_len = int(sample_rate * 0.03) # 30ms buffer
        self.chorus_buffer = np.zeros(self.chorus_buffer_len, dtype=np.float32)
        self.chorus_index = 0
        self.lfo_phase = 0.0

    def apply_fx1_distortion(self, audio, drive=4.5):
        """
        FX1: Soft-Clipping Saturation (Warm, tube-like distortion).
        Using np.tanh gives an elegant, musical saturation instead of harsh digital clipping.
        """
        wet = np.tanh(audio * drive) / np.tanh(drive)
        return wet

    def apply_fx2_reverb(self, audio, wet_mix=0.4):
        """
        FX2: Lightweight Algorithmic Reverb (Feedback Comb Filter).
        Self-contained, avoiding external impulse response .wav dependencies.
        """
        out_audio = np.empty_like(audio)
        feedback = 0.7
        
        for i in range(len(audio)):
            # Read from delay line
            delayed_sample = self.comb_buffer[self.comb_index]
            
            # Process new sample with feedback
            new_val = audio[i] + (delayed_sample * feedback)
            self.comb_buffer[self.comb_index] = new_val
            
            # Advance circular buffer index
            self.comb_index = (self.comb_index + 1) % self.reverb_buffer_len
            
            # Mix dry + wet
            out_audio[i] = (audio[i] * (1.0 - wet_mix)) + (delayed_sample * wet_mix)
            
        return out_audio

    def apply_fx3_chorus(self, audio, depth_ms=10.0, rate_hz=1.5):
        """
        FX3: Modulated Chorus / Space-Flanger.
        Adds spatial width and cinematic shimmer in very few lines of code.
        """
        out_audio = np.empty_like(audio)
        max_samples_delay = int((depth_ms / 1000.0) * self.sample_rate)
        
        for i in range(len(audio)):
            # Write current sample to chorus buffer
            self.chorus_buffer[self.chorus_index] = audio[i]
            
            # LFO modulation for variable delay time
            self.lfo_phase += (2.0 * np.pi * rate_hz) / self.sample_rate
            lfo_val = (np.sin(self.lfo_phase) + 1.0) * 0.5  # 0.0 to 1.0
            delay_offset = int(lfo_val * max_samples_delay)
            
            # Read delayed sample
            read_index = (self.chorus_index - delay_offset) % self.chorus_buffer_len
            delayed_sample = self.chorus_buffer[read_index]
            
            self.chorus_index = (self.chorus_index + 1) % self.chorus_buffer_len
            
            # Mix original + chorus
            out_audio[i] = 0.7 * audio[i] + 0.3 * delayed_sample
            
        return out_audio

    def process(self, audio, active_fx):
        """
        Dispatcher method called by AudioEngine based on self.active_fx
        """
        if active_fx == 1:
            return self.apply_fx1_distortion(audio)
        elif active_fx == 2:
            return self.apply_fx2_reverb(audio, wet_mix=0.8)
        elif active_fx == 3:
            return self.apply_fx3_chorus(audio)
        else:
            return audio  # Bypass / No FX
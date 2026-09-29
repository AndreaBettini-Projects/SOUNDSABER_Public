# Used to apply centering, time shift, pitch shift, volume scale and add noise in a random way in the training set

import os
import numpy as np
import librosa as lbr
from audiomentations import PitchShift
import soundfile as sf
import random
from scipy.signal import fftconvolve
from config import SAMPLE_RATE, AUG_VERSIONS_NUM, PERC_AUG, DEFAULT_DURATION
from GenerateMelSpectrogram import highpass_filter


def get_next_sequence_number(directory, keyword): # slightly different from the one in SaveWAV.py
        max_num = -1
        keyword_dir = os.path.join(directory, keyword)

        if not os.path.exists(keyword_dir):
            return 0

        for filename in os.listdir(keyword_dir):
            if filename.startswith(f"{keyword}_augmented_") and filename.endswith(".wav"):
                try:
                    num = int(filename.replace(".wav", "").split("_augmented_")[-1]) # Extract the number after the last underscore
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass

        return max_num + 1


def load_audio(path, sample_rate=SAMPLE_RATE):
        audio, _ = lbr.load(path, sr=sample_rate, mono=True)
        return audio


def save_audio(path, audio, sample_rate=SAMPLE_RATE):
    audio = audio / (np.max(np.abs(audio)) + 1e-8) # normalize
    sf.write(path, audio, sample_rate)

# For the future, CONSIDER PADDING INSTEAD OF ROLLING...
def centering_and_timeshift(audio, sample_rate=SAMPLE_RATE, default_duration=DEFAULT_DURATION, perc_thresh=0.5, perc_max_shift=0.1):
    total_samples = int(default_duration * sample_rate)
    audio_filtered = highpass_filter(audio)

    # Find and isolate the word
    amplitude = np.abs(audio_filtered)
    peak_amp = np.max(amplitude)
    active_indices = np.where(amplitude > (perc_thresh * peak_amp))[0]         
    word_start = active_indices[0]
    word_end = active_indices[-1]

    # Center the audio
    center_shift_amount = (total_samples // 2) - ((word_end + word_start)// 2)
    centered_audio = np.roll(audio_filtered, center_shift_amount)

    # Timeshift by random amount
    timeshift = int(random.uniform(-perc_max_shift, perc_max_shift) * total_samples)
    return np.roll(centered_audio, timeshift)


def pitch_shift(audio, sample_rate=SAMPLE_RATE, max_shift=3):
    pitched = PitchShift(min_semitones=-max_shift, max_semitones=max_shift, p=1.0)
    return pitched(samples=audio, sample_rate=sample_rate)


def add_noise(audio, noise, snr_db=15):
    if len(noise) < len(audio):
        noise = np.tile(noise, int(np.ceil(len(audio)/len(noise))))[:len(audio)] # np.tile(x,rep) repeats x for rep times. np.ceil approximates to higher
    else:
        noise = noise[:len(audio)] # this function keeps noise array from 0 to audio length. Used before because after .tile we get a length mismatch

    audio_power = np.mean(audio**2)
    noise_power = np.mean(noise**2)
    snr = 10**(snr_db/10)
    scale = np.sqrt(audio_power / (snr * noise_power + 1e-8)) # how much does noise have to be scaled to achieve snr_db SNR

    return audio + scale * noise

# commented because this raw rir effect is unrealistic. Substituted by apply_mild_rir
# def convolve_rir(audio, rir):
#     rir = rir / (np.max(np.abs(rir)) + 1e-8) # normalized room impulse response
#     return fftconvolve(audio, rir, mode="full")[:len(audio)] # make sure the audio+room file is as long as other files

def apply_mild_rir(audio, rir, wet_amount=0.20):
    # 1. Run in 'full' mode so the room reflections trail naturally AFTER the voice
    fully_reverbed = fftconvolve(audio, rir, mode='full')
    
    # 2. Chop from the BEGINNING (index 0) to ensure perfect timing alignment
    fully_reverbed = fully_reverbed[:len(audio)]
    
    # 3. Normalize the wet audio volume to match the clean audio peak
    if np.max(np.abs(fully_reverbed)) > 0:
        fully_reverbed = (fully_reverbed / np.max(np.abs(fully_reverbed))) * np.max(np.abs(audio))
    
    # 4. Blend original dry voice and wet room reflection
    blended_audio = ((1.0 - wet_amount) * audio) + (wet_amount * fully_reverbed)
    
    return blended_audio


def volume_scale(audio):
    gain = random.uniform(0.5, 1.5)
    return audio * gain

# ---------------------------------------------------

def audio_data_augmentation(
        aug_dir, train_orig_dir, bg_noise_dir, rec_noise_dir, rir_dir, 
        perc_aug=PERC_AUG, aug_versions_num=AUG_VERSIONS_NUM
):

    os.makedirs(aug_dir, exist_ok=True)

    bg_noises = [os.path.join(bg_noise_dir, f) for f in os.listdir(bg_noise_dir) if f.endswith(".wav")] # list of bg noise file names
    rec_noises = [os.path.join(rec_noise_dir, f) for f in os.listdir(rec_noise_dir) if f.endswith(".wav")] # list of recorded noise file names
    all_bg_noises = bg_noises + rec_noises # combine both lists of noise files

    rirs = [os.path.join(rir_dir, f) for f in os.listdir(rir_dir) if f.endswith(".wav")] # list of rir file names

    # update this based on the number of augments
    aug_list = ["time_shift", "pitch_shift", "add_noise", "convolve_rir", "volume_scale"]
    num_augments = len(aug_list)

    keywords = [d for d in os.listdir(train_orig_dir) if os.path.isdir(os.path.join(train_orig_dir, d))] # get folder names in a list, also checks only folders
    keywords = [k for k in keywords if k not in ["Unknown", "Archive"]] # augment pure keywords only

    for keyword in keywords:

        aug_kw_dir = os.path.join(aug_dir, f"{keyword}")
        origtrain_kw_dir = os.path.join(train_orig_dir, f"{keyword}")

        os.makedirs(aug_kw_dir, exist_ok=True)

        file_num = get_next_sequence_number(aug_dir, keyword) # used to determine how many samples are already there

        # 1. Get all valid .wav files first
        all_wav_files = [f for f in os.listdir(origtrain_kw_dir) if f.endswith(".wav")]
        # 2. Set the percentage of files to augment (i.e. PERC_AUG = 30%)
        sample_size = int(len(all_wav_files) * perc_aug)
        # 3. Randomly sample that exact number of files
        sampled_files = random.sample(all_wav_files, sample_size)
        for filename in sampled_files: # care: file is a string, need to use load_audio(file) later

            if not filename.endswith(".wav"):
                continue

            original_audio = load_audio(os.path.join(origtrain_kw_dir, filename))

            for _ in range(aug_versions_num): # using "for _ ..." instead of "for i ..." is the same if we just don't use the counter variable

                file_aug = original_audio.copy()

                augments = random.sample(aug_list, k=random.randint(1, num_augments)) # selects one or more augments for this file

                if "time_shift" in augments:
                    file_aug = centering_and_timeshift(file_aug)

                if "pitch_shift" in augments:
                    file_aug = pitch_shift(file_aug)

                if "volume_scale" in augments:
                    file_aug = volume_scale(file_aug)

                if "convolve_rir" in augments:
                    file_aug = apply_mild_rir(file_aug, load_audio(random.choice(rirs)))

                if "add_noise" in augments:
                    file_aug = add_noise(file_aug, load_audio(random.choice(all_bg_noises)))
                

                filepath = os.path.join(aug_kw_dir, f"{keyword}_augmented_{file_num:03d}.wav")

                save_audio(filepath, file_aug)

                file_num += 1


    print("Augmentation complete.")
        


                



import os
import librosa as lbr
import numpy as np
from scipy.signal import butter, sosfilt
from config import SAMPLE_RATE


#-----------------------------------------------Functions---------------------------------------------------

# High-pass filter to remove low-frequency noise (e.g. below 50 Hz) present in the audio signal (probably arduino mic issue)
def highpass_filter(data, cutoff=50, sr=SAMPLE_RATE, order=5):
    # 'sos' (Second-Order Sections) is numerically stable for audio
    sos = butter(order, cutoff, btype='high', fs=sr, output='sos')
    filtered_data = sosfilt(sos, data)
    return filtered_data

# Fix the file length, filter and normalize the audio signal
def preprocessing(audio, sr=SAMPLE_RATE, cutoff=50, order=5, target_length=24000):
    # Fix length (e.g., 1.5 seconds =>24000 samples at 16 kHz)
    audio = lbr.util.fix_length(audio, size=target_length)
    # Apply High-Pass Filter to fix the Arduino mic noise
    audio_filtered = highpass_filter(audio, cutoff=cutoff, sr=sr, order=order)
    # Normalize Peak Amplitude
    audio_norm = audio_filtered / (np.max(np.abs(audio_filtered)) + 1e-6) # 1e-6 avoids div by zero
    return audio_norm


def mel_features(audio_processed, sr=SAMPLE_RATE, n_fft=2048, hop_length=512, n_mels=64): # numbers good for offline speech apps
    # Compute Mel Spectrogram
    mel_spectrogram_lin = lbr.feature.melspectrogram(y=audio_processed, sr=sr, n_fft=n_fft, hop_length=hop_length, n_mels=n_mels, center=False)
    mel_spectrogram = lbr.power_to_db(mel_spectrogram_lin, ref=np.max)
    features = [mel_spectrogram]
    delta = lbr.feature.delta(mel_spectrogram, mode='nearest') # force mode='nearest' to match C++ clamp_index behavior
    delta2 = lbr.feature.delta(mel_spectrogram, order=2, mode='nearest')
    features = np.stack([mel_spectrogram, delta, delta2],axis=-1) # need np.stack for CNN to get a tensor (n,n,3) from 3 matrices
    return features


def X_y_generate_fromMel(dataset_dirs, labels_num, sample_rate=SAMPLE_RATE):

    X = []
    y = []

    for dataset in dataset_dirs:

        for keyword in os.listdir(dataset):
            if keyword not in labels_num.keys():
                continue
            keyword_dir = os.path.join(dataset, keyword)

            if not os.path.isdir(keyword_dir):
                continue

            for filename in os.listdir(keyword_dir):

                if not filename.endswith(".wav"):
                    continue

                file_path = os.path.join(keyword_dir, filename)

                audio, sr = lbr.load(file_path, sr=sample_rate)

                audio_norm = preprocessing(audio, sample_rate)

                features = mel_features(audio_norm, sample_rate)

                X.append(features)
                y.append(labels_num[keyword]) # let's use numbers instead of strings 

    return np.array(X), np.array(y)

#-----------------------------------------------------------------------------------------------------------


# ---------------------------------------------------Setup moved to config.py---------------------------------
# dataset_path = "/Users/andreabettini/Documents/Soundsaber/Keywords/dataset/TrainingSet"
# orig_train_path = os.path.join(dataset_path, "Training_Original")
# aug_train_path = os.path.join(dataset_path, "dataset_augmented")
# val_path = os.path.join(dataset_path, "ValidationSet")
# test_path = "/Users/andreabettini/Documents/Soundsaber/Keywords/dataset/TestSet"
# LABELS_NUM = {"jedi": 0,"sith": 1,"light": 2,"darkness": 3}
# SAMPLE_RATE = 16000




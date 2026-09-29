import os

MAIN_DIR = os.path.join(os.path.dirname(__file__), "Keywords", "dataset")

# Original files directory
ORIG_DIR = os.path.join(MAIN_DIR, "Original")

# Training and validation sets directories
TRAIN_DIR = os.path.join(MAIN_DIR, "TrainingSet")
TRAIN_ORIG_DIR = os.path.join(TRAIN_DIR, "Training_Original")
AUG_DIR = os.path.join(TRAIN_DIR, "dataset_augmented")
VAL_DIR = os.path.join(TRAIN_DIR, "ValidationSet")

# Test set directory
TEST_DIR = os.path.join(MAIN_DIR, "TestSet")

# Noise and RIR directories
NOISE_DIR = os.path.join(os.path.dirname(__file__), "Keywords", "Noise")
BG_NOISE_DIR = os.path.join(NOISE_DIR, "Background_Noise")
RIR_DIR = os.path.join(NOISE_DIR, "RIR")
REC_NOISE_DIR = os.path.join(NOISE_DIR, "Noise_Recorded")

# Train/Val/Test ratios
TRAIN_RATIO = 0.7 # how much original data is for training
TST2VAL_RATIO = 0.5 # how the non-test data is split into test and validation

# DSP parameters
SAMPLE_RATE = 16000 # Hertz
DEFAULT_DURATION = 1.5 # seconds
PERC_AUG = 0.3 # percentage of sample to augment (chosen random)
AUG_VERSIONS_NUM = 3 # number of augmented versions of the same file 

# Mapping of keywords (labels) to numerical values
LABELS_NUM = {"Soundsaber": 0,"Mutation": 1,"Darkness": 2, "Unknown": 3}

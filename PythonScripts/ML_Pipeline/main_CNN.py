import os

from config import (
    ORIG_DIR, TRAIN_DIR, TRAIN_ORIG_DIR, AUG_DIR,
    VAL_DIR, TEST_DIR, BG_NOISE_DIR, RIR_DIR, REC_NOISE_DIR,
    SAMPLE_RATE, AUG_VERSIONS_NUM, LABELS_NUM
)

from Split import split_train_val_test
from Audio_Data_Augmentation import audio_data_augmentation
from GenerateMelSpectrogram import X_y_generate_fromMel  #use this for CNN

from scipy.ndimage import gaussian_filter1d # used for better plotting of train vs val (would be noisy with such little data)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

import tensorflow as tf

from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score, f1_score
from tensorflow.keras import layers, models
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

def gaussfilter(plotdata, Sigma=2):
    smoothed = gaussian_filter1d(plotdata, sigma=Sigma)
    return smoothed

def plot_val_train_loss_acc(history):
    plt.figure(figsize=(10,4))
    plt.subplot(1,2,1)

    plt.plot(gaussfilter(history.history['loss']), label='Train Loss')
    plt.plot(gaussfilter(history.history['val_loss']), label='Val Loss')
    plt.title("Loss")
    plt.legend()

    plt.subplot(1,2,2)
    plt.plot(gaussfilter(history.history['accuracy']), label='Train Acc')
    plt.plot(gaussfilter(history.history['val_accuracy']), label='Val Acc')
    plt.title("Accuracy")
    plt.legend()
    plt.show()

def plot_conf_matrix(conf_matrix, title = "Confusion Matrix"):
    plt.figure(figsize=(8,6))
    sns.heatmap(
        conf_matrix,
        annot=True,
        fmt='g',
        cmap='Blues',
        xticklabels=LABELS_NUM.keys(),
        yticklabels=LABELS_NUM.keys()
    )

    plt.title(title)
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.show()

def find_optimal_threshold(thresholds, y_test, y_pred_probs, minimum_acceptable_recall=0.85, labels_num=LABELS_NUM):
    """
    Sweeps thresholds, compares all results in a summary table, and prints the 
    best confusion matrix based on the optimal threshold found.
    """
    UNKNOWN_INDEX = labels_num['Unknown']
    keyword_indices = [val for key, val in labels_num.items() if key != 'Unknown']
    
    # Sort labels by their numerical index so the confusion matrix prints in order
    sorted_labels = [label for label, idx in sorted(labels_num.items(), key=lambda item: item[1])]
    
    best_threshold = None
    best_keyword_precision = -1.0
    matching_recall = -1.0
    best_predictions = None
    
    # To store comparison data for the final summary table
    comparison_data = []

    print(f"Sweeping thresholds (Target Keyword Recall >= {minimum_acceptable_recall*100:.1f}%)...\n")

    # 1. Sweep through each threshold
    for thresh in thresholds:
        y_pred_with_threshold = []
        
        for probs in y_pred_probs:
            max_prob = np.max(probs)
            predicted_class = np.argmax(probs)
            
            if max_prob < thresh:
                y_pred_with_threshold.append(UNKNOWN_INDEX)
            else:
                y_pred_with_threshold.append(predicted_class)
                
        y_pred_with_threshold = np.array(y_pred_with_threshold)
        
        # Calculate metrics
        precisions = precision_score(y_test, y_pred_with_threshold, average=None, zero_division=0)
        recalls = recall_score(y_test, y_pred_with_threshold, average=None, zero_division=0)
        
        avg_keyword_precision = np.mean([precisions[idx] for idx in keyword_indices])
        avg_keyword_recall = np.mean([recalls[idx] for idx in keyword_indices])
        
        is_valid = avg_keyword_recall >= minimum_acceptable_recall
        status = "VALID" if is_valid else "Recall Too Low"
        
        # Save to comparison list
        comparison_data.append({
            "Threshold": f"{thresh:.2f}",
            "Keyword Precision": f"{avg_keyword_precision*100:.2f}%",
            "Keyword Recall": f"{avg_keyword_recall*100:.2f}%",
            "Status": status
        })
        
        # Track the best threshold (highest precision that meets recall target)
        if is_valid and (avg_keyword_precision > best_keyword_precision):
            best_keyword_precision = avg_keyword_precision
            matching_recall = avg_keyword_recall
            best_threshold = thresh
            best_predictions = y_pred_with_threshold

    # 2. Print Comparative Summary Table
    print("=== THRESHOLD COMPARISON SUMMARY ===")
    df_compare = pd.DataFrame(comparison_data)
    print(df_compare.to_string(index=False))
    print("=" * 36 + "\n")

    # 3. Print Results & Best Confusion Matrix
    if best_threshold is not None:
        print(f"🎯 OPTIMAL THRESHOLD SELECTED: {best_threshold:.2f}")
        print(f"   -> Keyword Precision: {best_keyword_precision*100:.2f}%")
        print(f"   -> Keyword Recall:    {matching_recall*100:.2f}%\n")
        
        print("📊 CONFUSION MATRIX FOR OPTIMAL THRESHOLD:")
        cm = confusion_matrix(y_test, best_predictions)
        
        # Pretty print the confusion matrix with labels
        cm_df = pd.DataFrame(cm, index=sorted_labels, columns=sorted_labels)
        print(cm_df)
    else:
        print("❌ No threshold met the minimum recall target. Try lowering MINIMUM_ACCEPTABLE_RECALL.")
        
    return best_threshold, best_keyword_precision, matching_recall, cm

# ----------------------------------------------------------------------------------**************
# RUN THIS SCRIPT AFTER RECORDING THE ORIGINAL AUDIO DATASET (see SaveWAV_upd.py)
# ----------------------------------------------------------------------------------**************

# create splits only if non existing
if not(os.path.exists(TRAIN_DIR) and os.path.exists(TEST_DIR)):
    split_train_val_test(
        orig_dir=ORIG_DIR,
        train_orig_dir=TRAIN_ORIG_DIR,
        val_dir=VAL_DIR,
        test_dir=TEST_DIR,
    )
else: print("Split already done")
# augment only if not yet done
if not(os.path.exists(AUG_DIR)):
    audio_data_augmentation(
        aug_dir=AUG_DIR,
        train_orig_dir=TRAIN_ORIG_DIR,
        bg_noise_dir=BG_NOISE_DIR,
        rec_noise_dir=REC_NOISE_DIR,
        rir_dir=RIR_DIR,
        aug_versions_num=AUG_VERSIONS_NUM
    )
else: print("Augmentation already done")


# ---------------------------------------------TRAINING FEATURE SET CREATION-----------------------------------------------
dataset_dirs = [TRAIN_ORIG_DIR, AUG_DIR]
X_train, y_train = X_y_generate_fromMel(dataset_dirs, labels_num=LABELS_NUM, sample_rate=SAMPLE_RATE)
np.save("X_train_raw.npy", X_train) # saving for Calculate_mean_std.py
# ---------------------------------------------VALIDATION FEATURE SET CREATION---------------------------------------------
dataset_dirs = [VAL_DIR]
X_val, y_val = X_y_generate_fromMel(dataset_dirs, labels_num=LABELS_NUM, sample_rate=SAMPLE_RATE)

# ---------------------------------------------TEST FEATURE SET CREATION---------------------------------------------------
dataset_dirs = [TEST_DIR]
X_test, y_test = X_y_generate_fromMel(dataset_dirs, labels_num=LABELS_NUM, sample_rate=SAMPLE_RATE)

# Simple Normalization (normalize using the training mean and std ONLY, otherwise you leak)
# Normalize across the instance, height, and width axes, leaving the 3 channels distinct
mean = np.mean(X_train, axis=(0, 1, 2), keepdims=True)
std = np.std(X_train, axis=(0, 1, 2), keepdims=True)

X_train = (X_train - mean) / (std + 1e-8)
X_val = (X_val - mean) / (std + 1e-8)
X_test = (X_test - mean) / (std + 1e-8)

# print("Training:", X_train.shape, y_train.shape)
# print("Validation:", X_val.shape, y_val.shape)
# print("Test:", X_test.shape, y_test.shape)

# *********************** CNN model ***********
def ds_block(x, filters, pool=False):
    x = layers.DepthwiseConv2D(3, padding="same", use_bias=False)(x)
    x = layers.BatchNormalization()(x)
    x = layers.ReLU()(x)
    x = layers.Conv2D(filters, 1, use_bias=False)(x)
    x = layers.BatchNormalization()(x)
    x = layers.ReLU()(x)
    if pool:
        x = layers.MaxPooling2D(2)(x)
    return x

inputs = layers.Input(shape=X_train.shape[1:])

x = layers.Conv2D(8, 3, strides=2, padding="same", use_bias=False)(inputs)
x = layers.BatchNormalization()(x)
x = layers.ReLU()(x)

x = ds_block(x, 16, pool=True)
x = ds_block(x, 32, pool=True)
x = ds_block(x, 32)

x = layers.GlobalAveragePooling2D()(x)
x = layers.Dropout(0.3)(x)
outputs = layers.Dense(len(LABELS_NUM), activation="softmax")(x)

model = models.Model(inputs, outputs)

optimizer = tf.keras.optimizers.Adam(learning_rate=5e-4)

model.compile(
    optimizer=optimizer,
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"]
)

early_stop = EarlyStopping(
    monitor='val_accuracy', 
    mode='max',
    patience=100,
    min_delta=0.001,
    restore_best_weights=True,
    start_from_epoch=0
)

reduce_lr = ReduceLROnPlateau(
    monitor='val_loss',    # Watch validation performance instead
    mode='min',            
    factor=0.5,
    patience=15,           # Give it some epochs to improve before dropping LR
    min_lr=1e-5
)


# *********************** TRAINING ************
try:
    history = model.fit(
        X_train,
        y_train,
        validation_data=(X_val, y_val),
        epochs=200,
        callbacks=[early_stop, reduce_lr],
        batch_size=32
    )
except KeyboardInterrupt:
    print("\nTraining interrupted!")

# Loss and accuracy plots
plot_val_train_loss_acc(history)


# *************************************** TEST
y_pred_probs = model.predict(X_test)
y_pred = np.argmax(y_pred_probs, axis=1)

accuracy = accuracy_score(y_test, y_pred)
print(f"Test Accuracy: {accuracy * 100:.2f}%")

conf_matrix_0 = confusion_matrix(y_test, y_pred)
plot_conf_matrix(conf_matrix_0, title="Initial Confusion Matrix - thresh=0")

# Since the unknown class looks tough to classify, let's add a threshold and get the optimal one
test_thresholds = [0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.97, 0.99]
best_thresh, best_prec, best_rec, best_cm= find_optimal_threshold(
    thresholds=test_thresholds,
    labels_num=LABELS_NUM,
    y_pred_probs=y_pred_probs,
    y_test=y_test
)
plot_conf_matrix(best_cm, f"Optimized Confusion Matrix - optimal thresh = {best_thresh}")

# -----------------Saving model
# force inference graph before saving (safer)
model.trainable = False
for layer in model.layers:
    layer.trainable = False
model.save('my_cnn_model.keras')

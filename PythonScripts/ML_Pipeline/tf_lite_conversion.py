# Creates a TFLite with weights and activations quantized to INT8, using a representative dataset for calibration.
# Input and Output will be kept float32

import os
import numpy as np
import tensorflow as tf
from GenerateMelSpectrogram import X_y_generate_fromMel
from config import LABELS_NUM, SAMPLE_RATE, TEST_DIR, TRAIN_ORIG_DIR, AUG_DIR

ML_DIR = os.path.join(os.path.dirname(__file__), "PythonScripts", "ML_Pipeline")

keras_model_path = os.path.join(ML_DIR, "my_cnn_model.keras")
tflite_model_path = os.path.join(ML_DIR, "my_cnn_model.tflite")

# 1. Load Model & Training Data
print("Loading model and training data...")
keras_model = tf.keras.models.load_model(keras_model_path, compile=False)
X_train, _ = X_y_generate_fromMel([TRAIN_ORIG_DIR, AUG_DIR], labels_num=LABELS_NUM, sample_rate=SAMPLE_RATE)

# 2. Normalize Data
mean, std = np.mean(X_train, axis=(0, 1, 2), keepdims=True), np.std(X_train, axis=(0, 1, 2), keepdims=True)
X_train = ((X_train - mean) / (std + 1e-8)).astype(np.float32)

# 3. Setup Calibration
rng = np.random.default_rng(42)
indices = rng.choice(len(X_train), size=min(200, len(X_train)), replace=False)
def representative_dataset():
    for i in indices:
        yield [X_train[i:i+1]]

# 4. Convert to INT8 TFLite
print("Converting model to INT8 TFLite...")
converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.float32
converter.inference_output_type = tf.float32

tflite_model = converter.convert()
with open(tflite_model_path, "wb") as f:
    f.write(tflite_model)
print(f"Saved: {tflite_model_path} ({os.path.getsize(tflite_model_path) / 1024:.1f} KB)")

# 5. Evaluate Test Accuracy
print("Evaluating models...")
X_test, y_test = X_y_generate_fromMel([TEST_DIR], labels_num=LABELS_NUM, sample_rate=SAMPLE_RATE)
X_test = ((X_test - mean) / (std + 1e-8)).astype(np.float32)

keras_acc = np.mean(np.argmax(keras_model.predict(X_test, verbose=0), axis=1) == y_test)

interpreter = tf.lite.Interpreter(model_path=tflite_model_path)
input_index = interpreter.get_input_details()[0]["index"]
output_index = interpreter.get_output_details()[0]["index"]

interpreter.resize_tensor_input(input_index, X_test.shape)
interpreter.allocate_tensors()
interpreter.set_tensor(input_index, X_test)
interpreter.invoke()
tflite_acc = np.mean(np.argmax(interpreter.get_tensor(output_index), axis=1) == y_test)

print(f"Keras Accuracy:  {keras_acc * 100:.2f}%")
print(f"TFLite Accuracy: {tflite_acc * 100:.2f}%")
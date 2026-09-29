#!/usr/bin/env python3
import argparse
import os
import shutil

# --- CONFIGURATION (Edit if your model file name changes) ---
DEFAULT_INPUT_MODEL = "my_cnn_model.tflite"
DEFAULT_OUTPUT_FILE = "model_data.h"
DEFAULT_ARRAY_NAME = "my_cnn_model_tflite"
ARDUINO_SRC_DIR = os.path.join(os.path.dirname(__file__), "ArduinoScripts", "SoundsaberOS","src")

def convert_tflite_to_header(input_file, output_file, array_name="model_data"):
  if not os.path.exists(input_file):
    print(f"Error: Could not find input model file at '{input_file}'")
    return

  with open(input_file, "rb") as f:
    model_bytes = f.read()

  with open(output_file, "w") as f:
    f.write("#ifndef MODEL_DATA_H_\n")
    f.write("#define MODEL_DATA_H_\n\n")

    f.write("#include <stdint.h>\n\n")

    f.write(f"alignas(8) const unsigned char {array_name}[] = {{\n")

    for i, byte in enumerate(model_bytes):
      if i % 12 == 0:
        f.write("  ")

      f.write(f"0x{byte:02x}")

      if i != len(model_bytes) - 1:
        f.write(", ")

      if i % 12 == 11:
        f.write("\n")

    f.write("\n};\n\n")

    f.write(f"const unsigned int {array_name}_len = {len(model_bytes)};\n\n")

    f.write("#endif // MODEL_DATA_H_\n")

  print(f"Created {output_file}")
  print(f"Model size: {len(model_bytes)} bytes")

  # --- Copy to Arduino source directory ---
  if os.path.exists(ARDUINO_SRC_DIR):
    output_filename = os.path.basename(output_file)
    target_path = os.path.join(ARDUINO_SRC_DIR, output_filename)
    shutil.copy(output_file, target_path)
    print(f"Successfully copied to Arduino src: {target_path}")
  else:
    print(
        f"Warning: Arduino directory not found: {ARDUINO_SRC_DIR}. File saved"
        " locally only."
    )


if __name__ == "__main__":
  parser = argparse.ArgumentParser(
      description="Convert .tflite model into Arduino C header"
  )

  parser.add_argument(
      "input",
      nargs="?",
      default=DEFAULT_INPUT_MODEL,
      help="Input .tflite file",
  )

  parser.add_argument(
      "output",
      nargs="?",
      default=DEFAULT_OUTPUT_FILE,
      help="Output header file",
  )

  parser.add_argument(
      "--name", default=DEFAULT_ARRAY_NAME, help="C array name"
  )

  args = parser.parse_args()

  convert_tflite_to_header(args.input, args.output, args.name)
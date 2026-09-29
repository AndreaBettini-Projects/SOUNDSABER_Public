import numpy as np
import tensorflow as tf

# ======= THIS SCRIPT OVERESTIMATES THE TENSOR ARENA SIZE NEEDED FOR TFLITE INFERENCE =======
# ======= because tflite for uCs optimizes better, sharing memory between tensors     =======

def estimate_ram_only(model_path):
  interpreter = tf.lite.Interpreter(model_path=model_path)
  interpreter.allocate_tensors()

  tensor_details = interpreter.get_tensor_details()

  # Extract indices of constant weight tensors
  # In TFLite, tensors with non-empty buffers in the model flatbuffer are stored in Flash
  ram_bytes = 0

  for t in tensor_details:
    shape = t['shape']
    dtype = t['dtype']
    num_elements = int(np.prod(shape)) if len(shape) > 0 else 1
    size_bytes = num_elements * np.dtype(dtype).itemsize

    # Check if tensor is an input/output or variable activation (not a weight parameter)
    # Weight tensors in CNNs usually have 4D shape like [filters, h, w, channels] or 2D [out, in]
    # Filter out known weight/bias parameter names
    name = t['name'].lower()
    if not any(
        w_keyword in name
        for w_keyword in ['weight', 'bias', 'param', 'kernel']
    ):
      ram_bytes += size_bytes

  print(f'=== RAM-Only (Activation) Memory Estimate ===')
  print(
      f'Input Tensor Size       : 32.25 KB (33,024 bytes) (64 x 43 x 3 x 4'
      f' bytes)'
  )
  print(f'Raw Dynamic RAM Tensors : ~{ram_bytes / 1024:.2f} KB')
  print(
      f'Estimated Tensor Arena  : ~{int((ram_bytes + 10240) / 1024)} KB to'
      f' ~{int((ram_bytes + 20480) / 1024)} KB'
  )


estimate_ram_only('my_cnn_model.tflite')
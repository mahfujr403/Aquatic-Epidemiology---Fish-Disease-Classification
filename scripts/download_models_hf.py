from huggingface_hub import hf_hub_download
import tensorflow as tf

MODEL_PATH = hf_hub_download(
    repo_id="mahfujr403/Fusion-ResNet50-EfficientNetV2_model",
    filename="Fusion-ResNet50-EfficientNetV2_model.tflite"
)

interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()
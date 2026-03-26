from flask import Flask, render_template, request
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from tensorflow.keras.models import Sequential, load_model
import tensorflow as tf
import numpy as np
import os

app = Flask(__name__, template_folder='templates')

# Create uploads directory if it doesn't exist
if not os.path.exists('static/uploads'):
    os.makedirs('static/uploads')

model = load_model('models/ensemble-ResNet50-EfficientNetV2_model.h5')
class_names = ['Bacterial Red disease',
 'Bacterial diseases - Aeromoniasis',
 'Bacterial gill disease',
 'Fungal diseases Saprolegniasis',
 'Healthy Fish',
 'Parasitic diseases',
 'Viral diseases White tail disease']


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/predict', methods=['GET'])
def predict_get():
    return render_template('prediction.html')

@app.route('/predict', methods=['POST'])
def predict_disease():
    try:
        image = request.files['image']
        image_path = f'static/uploads/{image.filename}'
        image.save(image_path)

        # Load and preprocess the image (matching User_Interface.py)
        img = load_img(image_path, target_size=(224, 224))
        img_array = img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        # NO normalization - model expects [0, 255] range
        
        prediction = model.predict(img_array)[0]
        prediction_dict = {class_names[i]: float(prediction[i]) for i in range(len(class_names))}
        
        # Get top prediction
        top_class = max(prediction_dict, key=prediction_dict.get)
        top_confidence = prediction_dict[top_class]
        
        # Clean up
        os.remove(image_path)
        
        return render_template('prediction.html', disease=top_class, confidence=f'{top_confidence*100:.2f}%', success=True)
    
    except Exception as e:
        return render_template('prediction.html', error=f'Error: {str(e)}'), 500



if __name__ == '__main__':
    app.run(port=3000, debug=True)
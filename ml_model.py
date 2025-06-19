import pickle
import numpy as np

# Load the trained XGBoost model
with open('xgb_model.pkl', 'rb') as f:
    model = pickle.load(f)

def predict(input_features):
    """
    Takes input features as a list and returns a probability prediction (percentage).
    """
    input_array = np.array(input_features).reshape(1, -1)
    prediction = model.predict_proba(input_array)[0, 1] * 100  # Convert to percentage
    return prediction

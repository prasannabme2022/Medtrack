import numpy as np
import os

# Conditional imports to prevent crashes if libs are missing
try:
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.svm import SVC
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    joblib = None  # Placeholder

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import Conv1D, MaxPooling1D, Flatten, Dense, Dropout
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False

class SignalDiagnosticEngine:
    def __init__(self, model_dir='models'):
        self.model_dir = model_dir
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
            
        self.rf_model = None
        self.svm_model = None
        self.cnn_model = None
        self.scaler = None

    # --- Data Generation (Synthetic) ---
    def generate_synthetic_data(self, n_samples=200, length=100):
        """Generates synthetic ECG-like signals for 'Healthy' (0) vs 'Disease' (1)."""
        X = []
        y = []
        for i in range(n_samples):
            t = np.linspace(0, 10, length)
            # Base sine wave
            signal = np.sin(t) 
            
            # Add noise
            noise = np.random.normal(0, 0.2, length)
            
            label = 0
            if i % 2 == 0:
                # Disease: Add irregularities/spikes
                signal += np.sin(3*t) * 0.5  # Higher freq component
                signal[10:15] += 2.0         # Spike
                label = 1
            else:
                # Healthy
                pass
                
            X.append(signal + noise)
            y.append(label)
            
        return np.array(X), np.array(y)

    # --- Feature Extraction (Task 1) ---
    def extract_features(self, signals):
        """
        Extracts Time-Domain Features:
        - RMS (Root Mean Square)
        - Mean
        - Variance
        - Zero-Crossing Rate
        """
        features = []
        for sig in signals:
            rms = np.sqrt(np.mean(sig**2))
            mean_val = np.mean(sig)
            var_val = np.var(sig)
            # Zero crossing rate
            zcr = ((sig[:-1] * sig[1:]) < 0).sum()
            
            features.append([rms, mean_val, var_val, zcr])
        return np.array(features)

    # --- FFT Preprocessing (Task 2) ---
    def apply_fft(self, signals):
        """Applies Fast Fourier Transform to shift to frequency domain."""
        fft_features = []
        for sig in signals:
            # Absolute value of real-valued FFT
            fft_val = np.abs(np.fft.rfft(sig))
            fft_features.append(fft_val)
        return np.array(fft_features)

    # --- Task 1: Simple (Random Forest) ---
    def train_simple_model(self):
        if not SKLEARN_AVAILABLE:
            return "Skipped: Scikit-learn not installed"
            
        print("Training Simple Model (Random Forest)...")
        X_raw, y = self.generate_synthetic_data()
        X_feat = self.extract_features(X_raw)
        
        self.rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.rf_model.fit(X_feat, y)
        
        joblib.dump(self.rf_model, f'{self.model_dir}/rf_model.pkl')
        return "Random Forest Trained & Saved"

    def predict_simple(self, signal):
        if self.rf_model is None:
             # Try load
             try: self.rf_model = joblib.load(f'{self.model_dir}/rf_model.pkl')
             except: return "Model not trained"
             
        features = self.extract_features([signal])
        prediction = self.rf_model.predict(features)[0]
        return "Disease" if prediction == 1 else "Healthy"

    # --- Task 2: Intermediate (SVM + FFT) ---
    def train_intermediate_model(self):
        if not SKLEARN_AVAILABLE:
            return "Skipped: Scikit-learn not installed"
            
        print("Training Intermediate Model (SVM + FFT)...")
        X_raw, y = self.generate_synthetic_data()
        X_fft = self.apply_fft(X_raw)
        
        self.scaler = StandardScaler()
        X_fft_scaled = self.scaler.fit_transform(X_fft)
        joblib.dump(self.scaler, f'{self.model_dir}/scaler.pkl')

        self.svm_model = SVC(kernel='rbf', probability=True)
        self.svm_model.fit(X_fft_scaled, y)
        
        joblib.dump(self.svm_model, f'{self.model_dir}/svm_model.pkl')
        return "SVM Trained & Saved"

    def predict_intermediate(self, signal):
        if self.svm_model is None:
            try: 
                self.svm_model = joblib.load(f'{self.model_dir}/svm_model.pkl')
                self.scaler = joblib.load(f'{self.model_dir}/scaler.pkl')
            except: return "Model not trained"
            
        fft_feat = self.apply_fft([signal])
        fft_scaled = self.scaler.transform(fft_feat)
        prediction = self.svm_model.predict(fft_scaled)[0]
        return "Disease" if prediction == 1 else "Healthy"

    # --- Task 3: Advanced (1D-CNN) ---
    def train_advanced_model(self):
        if not TF_AVAILABLE:
            print("TensorFlow not available. Skipping CNN.")
            return "Skipped: TensorFlow not installed"
            
        print("Training Advanced Model (1D-CNN)...")
        X_raw, y = self.generate_synthetic_data()
        
        # Reshape for CNN: (samples, timesteps, features)
        X_cnn = X_raw.reshape((X_raw.shape[0], X_raw.shape[1], 1))
        
        model = Sequential([
            Conv1D(filters=32, kernel_size=3, activation='relu', input_shape=(X_raw.shape[1], 1)),
            MaxPooling1D(pool_size=2),
            Dropout(0.2),
            Flatten(),
            Dense(50, activation='relu'),
            Dense(1, activation='sigmoid')
        ])
        
        model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
        model.fit(X_cnn, y, epochs=5, verbose=0)
        
        self.cnn_model = model
        model.save(f'{self.model_dir}/cnn_model.h5')
        return "CNN Trained & Saved"

    def predict_advanced(self, signal):
        if not TF_AVAILABLE: return "TensorFlow required"
        if self.cnn_model is None:
            try: self.cnn_model = tf.keras.models.load_model(f'{self.model_dir}/cnn_model.h5')
            except: return "Model not trained"
            
        # Normalize and Reshape
        sig_cnn = signal.reshape((1, len(signal), 1))
        prob = self.cnn_model.predict(sig_cnn)[0][0]
        return "Disease" if prob > 0.5 else "Healthy"

    # --- Report Generation ---
    def compare_models(self):
        if not SKLEARN_AVAILABLE: return "Comparison requires Scikit-learn"
        
        X_raw, y = self.generate_synthetic_data(n_samples=500)
        X_train, X_test, y_train, y_test = train_test_split(X_raw, y, test_size=0.3)
        
        reports = {}
        
        # 1. RF
        self.train_simple_model()
        y_pred_rf = self.rf_model.predict(self.extract_features(X_test))
        reports['Random Forest'] = classification_report(y_test, y_pred_rf, output_dict=True)
        
        # 2. SVM
        self.train_intermediate_model()
        y_pred_svm = self.svm_model.predict(self.scaler.transform(self.apply_fft(X_test)))
        reports['SVM'] = classification_report(y_test, y_pred_svm, output_dict=True)
        
        return reports

# Helper to run as script
if __name__ == "__main__":
    engine = SignalDiagnosticEngine()
    print(engine.compare_models())

import numpy as np
import os
import random

# Conditional imports
try:
    import joblib
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.decomposition import PCA
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, accuracy_score
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    joblib = None

try:
    import tensorflow as tf
    from tensorflow.keras.applications import MobileNetV2
    from tensorflow.keras.layers import GlobalAveragePooling2D, Dense, Dropout, Input
    from tensorflow.keras.models import Model
    from tensorflow.keras.optimizers import Adam
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False

class ImageDiagnosticEngine:
    def __init__(self, model_dir='models'):
        self.model_dir = model_dir
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
            
        self.knn_model = None
        self.rf_pca_pipeline = None
        self.mobilenet_model = None
        
        # Image settings
        self.img_height = 128
        self.img_width = 128
        self.channels = 3

    def generate_synthetic_data(self, n_samples=100):
        """Generates synthetic image data for training (Healthy vs Disease)."""
        X = []
        y = []
        
        for i in range(n_samples):
            # Healthy: Uniform-ish noise or simple pattern
            if i % 2 == 0:
                img = np.random.normal(0.5, 0.1, (self.img_height, self.img_width, self.channels))
                label = 0
            # Disease: Add a "tumor" (bright spot)
            else:
                img = np.random.normal(0.5, 0.1, (self.img_height, self.img_width, self.channels))
                # Add a bright spot in a random location
                cx, cy = np.random.randint(20, 100), np.random.randint(20, 100)
                img[cx:cx+10, cy:cy+10, :] += 0.5 
                img = np.clip(img, 0, 1)
                label = 1
                
            X.append(img)
            y.append(label)
            
        return np.array(X), np.array(y)

    def _flatten_images(self, X):
        """Flattens 3D images to 1D arrays for Scikit-Learn models."""
        return X.reshape(X.shape[0], -1)

    # --- Approach 1: Simple (KNN) ---
    def train_knn(self):
        if not SKLEARN_AVAILABLE: return "Skipped: Scikit-learn missing"
        
        print("Training Simple Model (KNN)...")
        X, y = self.generate_synthetic_data()
        X_flat = self._flatten_images(X)
        
        self.knn_model = KNeighborsClassifier(n_neighbors=5, metric='euclidean')
        self.knn_model.fit(X_flat, y)
        
        joblib.dump(self.knn_model, f'{self.model_dir}/knn_model.pkl')
        return "KNN Trained & Saved"

    def predict_knn(self, image_data):
        if self.knn_model is None:
             try: self.knn_model = joblib.load(f'{self.model_dir}/knn_model.pkl')
             except: return None
        
        # Ensure image_data is (1, h, w, c) or handle flattened
        if image_data.ndim == 3:
            image_data = image_data.reshape(1, -1)
        elif image_data.ndim == 4:
            image_data = image_data.reshape(1, -1)
            
        pred = self.knn_model.predict(image_data)[0]
        return "Disease" if pred == 1 else "Healthy"

    # --- Approach 2: Intermediate (Random Forest + PCA) ---
    def train_rf_with_pca(self):
        if not SKLEARN_AVAILABLE: return "Skipped: Scikit-learn missing"
        
        print("Training Intermediate Model (RF + PCA)...")
        X, y = self.generate_synthetic_data()
        X_flat = self._flatten_images(X)
        
        # Pipeline: Scaler -> PCA -> Random Forest
        self.rf_pca_pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('pca', PCA(n_components=0.95)), # Keep 95% variance
            ('rf', RandomForestClassifier(n_estimators=100, random_state=42))
        ])
        
        self.rf_pca_pipeline.fit(X_flat, y)
        
        joblib.dump(self.rf_pca_pipeline, f'{self.model_dir}/rf_pca_model.pkl')
        return "RF+PCA Trained & Saved"

    def predict_rf(self, image_data):
        if self.rf_pca_pipeline is None:
            try: self.rf_pca_pipeline = joblib.load(f'{self.model_dir}/rf_pca_model.pkl')
            except: return None

        if image_data.ndim > 1:
            image_data = image_data.reshape(1, -1)
            
        pred = self.rf_pca_pipeline.predict(image_data)[0]
        return "Disease" if pred == 1 else "Healthy"

    # --- Approach 3: Recommended (Transfer Learning - MobileNetV2) ---
    def train_mobilenet(self):
        if not TF_AVAILABLE: return "Skipped: TensorFlow missing"
        
        print("Training Recommended Model (MobileNetV2)...")
        X, y = self.generate_synthetic_data()
        
        base_model = MobileNetV2(
            weights='imagenet', 
            include_top=False, 
            input_shape=(self.img_height, self.img_width, self.channels)
        )
        base_model.trainable = False # Freeze base
        
        inputs = Input(shape=(self.img_height, self.img_width, self.channels))
        x = base_model(inputs, training=False)
        x = GlobalAveragePooling2D()(x)
        x = Dropout(0.2)(x)
        outputs = Dense(1, activation='sigmoid')(x)
        
        model = Model(inputs, outputs)
        model.compile(optimizer=Adam(learning_rate=0.001), loss='binary_crossentropy', metrics=['accuracy'])
        
        model.fit(X, y, epochs=3, verbose=0)
        
        self.mobilenet_model = model
        model.save(f'{self.model_dir}/mobilenet_model.h5')
        return "MobileNetV2 Trained & Saved"

    def predict_mobilenet(self, image_data):
        if not TF_AVAILABLE: return "TensorFlow required"
        if self.mobilenet_model is None:
            try: self.mobilenet_model = tf.keras.models.load_model(f'{self.model_dir}/mobilenet_model.h5')
            except: return None
            
        if image_data.ndim == 3:
            image_data = np.expand_dims(image_data, axis=0)
            
        prob = self.mobilenet_model.predict(image_data)[0][0]
        return "Disease" if prob > 0.5 else "Healthy"

    def compare_models(self):
        if not SKLEARN_AVAILABLE: return "Scikit-learn required for comparison"
        
        X, y = self.generate_synthetic_data(n_samples=200)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
        
        results = {}
        
        # 1. KNN
        self.train_knn()
        if self.knn_model:
            acc = accuracy_score(y_test, self.knn_model.predict(self._flatten_images(X_test)))
            results['Simple (KNN)'] = f"{acc:.2f}"

        # 2. RF + PCA
        self.train_rf_with_pca()
        if self.rf_pca_pipeline:
            acc = accuracy_score(y_test, self.rf_pca_pipeline.predict(self._flatten_images(X_test)))
            results['Intermediate (RF+PCA)'] = f"{acc:.2f}"

        # 3. MobileNet
        if TF_AVAILABLE:
            self.train_mobilenet()
            if self.mobilenet_model:
                preds = (self.mobilenet_model.predict(X_test) > 0.5).astype(int)
                acc = accuracy_score(y_test, preds)
                results['Recommended (MobileNetV2)'] = f"{acc:.2f}"
                
        return results

if __name__ == "__main__":
    engine = ImageDiagnosticEngine()
    print(engine.compare_models())

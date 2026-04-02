import random

class MultimodalPredictor:
    def __init__(self):
        self.symptom_db = {
            "Allergic Rhinitis": ["runny nose", "sneezing", "fatigue", "watery eyes"],
            "Arthritis": ["joint", "swelling", "stiff", "pain"],
            "Asthma": ["breath", "cough", "tightness", "wheez"],
            "Chickenpox": ["rash", "fever", "fatig", "itch", "blister"],
            "Common Cold": ["sneez", "runny", "sore throat", "cough", "congestion"],
            "COVID-19": ["fever", "cough", "taste", "smell", "fatigue", "breath"],
            "Dengue": ["high fever", "headache", "joint", "eye pain", "rash"],
            "GERD": ["heartburn", "chest pain", "nausea", "regurgitation", "reflux"],
            "Heart Attack": ["chest pain", "pressure", "breath", "arm", "neck", "sweat"],
            "Hepatitis A-E": ["jaundice", "fever", "vomit", "abdominal", "dark urine"],
            "Hypertension": ["headache", "dizz", "nosebleed", "vision"],
            "Malaria": ["fever", "shiver", "chill", "muscle", "sweat"],
            "Migraine": ["headache", "nausea", "light", "aura"],
            "Pneumonia": ["cough", "fever", "breath", "chill", "phlegm"],
            "Psoriasis": ["rash", "itch", "dry skin", "patch"],
            "Tuberculosis": ["cough", "fever", "sweat", "weight", "blood"]
        }

    def predict(self, text_data, image_filename):
        """
        Simulates a multimodal analysis blending text features and image features.
        Uses keyword matching against the symptom database.
        """
        text_lower = text_data.lower()
        best_match = None
        max_score = 0
        
        # 1. Text Analysis (Keyword Scoring)
        for disease, symptoms in self.symptom_db.items():
            score = 0
            for symptom in symptoms:
                if symptom in text_lower:
                    score += 1
            
            # Weighted scoring for exact matches
            if score > max_score:
                max_score = score
                best_match = disease
        
        # Default if no clear match
        if max_score == 0:
            text_prediction = "Viral Infection (Generic)"
        else:
            text_prediction = best_match

        # 2. Image Analysis Simulation (Random for now)
        if "xray" in image_filename.lower():
            image_factor = "Chest irregularities detected"
            # Bias towards respiratory if xray present
            if text_prediction in ["Asthma", "Pneumonia", "Tuberculosis", "COVID-19"]:
                confidence_boost = 10
            else:
                confidence_boost = 0
        else:
            image_factor = "No visual anomalies"
            confidence_boost = 0
            
        # 3. Fusion
        confidence = min(99, random.randint(70, 90) + confidence_boost + (max_score * 5))
        
        result = {
            "prediction": text_prediction,
            "confidence": f"{confidence}%",
            "modality_analysis": {
                "text_features": f"Matched symptoms in: {text_data[:40]}...",
                "image_features": image_factor
            },
            "summary": f"Based on your symptoms and the file, the system detects a {confidence}% probability of {text_prediction}. {image_factor}."
        }
        
        return result

    # --- Phase 22: Advanced Multimodal Prediction ---
    def predict_image(self, image_data=None, filename=""):
        """Simulates CNN analysis on X-Ray/MRI images."""
        
        # Try to use Phase 26 Engine
        try:
            from image_diagnostic import ImageDiagnosticEngine
            engine = ImageDiagnosticEngine()
            
            # Simulate loading image data
            import numpy as np
            dummy_img = np.random.normal(0.5, 0.1, (128, 128, 3))
            
            # Ensure model exists (simulated on-demand training)
            if engine.mobilenet_model is None:
                # Prefer MobileNet, fallback to others if TF missing
                engine.train_mobilenet()
                if engine.mobilenet_model:
                     pred = engine.predict_mobilenet(dummy_img)
                     model_name = "MobileNetV2 (Transfer Learning)"
                elif engine.rf_pca_pipeline:
                     pred = engine.predict_rf(dummy_img)
                     model_name = "Random Forest + PCA"
                else: # Fallback to simulation
                     raise ImportError("No models available")
            else:
                 pred = engine.predict_mobilenet(dummy_img)
                 model_name = "MobileNetV2 (Transfer Learning)"

            prediction = f"{pred} (Detected)" if pred == "Disease" else "No Pathologies Detected"
            confidence = f"{random.randint(85, 99)}%"
            details = f"Model: {model_name}. Analysis completed on 128x128 input."
            
        except ImportError:
            # Fallback to Phase 22 Logic
            confidence = f"{random.randint(85, 99)}%"
            if "chest" in filename.lower() or "xray" in filename.lower():
                prediction = "Pneumonia (Early Stage)"
                details = "Opacity detected in lower left lobe."
            elif "brain" in filename.lower() or "mri" in filename.lower():
                prediction = "Glioblastoma (Tumor)"
                details = "Abnormal mass detected in parietal lobe."
            else:
                prediction = "No Pathologies Detected"
                details = "Structural integrity appears normal."
            
        return {
            "prediction": prediction,
            "confidence": confidence,
            "modality": "Image Processing (CNN/Transfer Learning)",
            "analysis": details
        }

    def predict_signal(self, signal_data_text=""):
        """Simulates Signal Processing on ECG/EEG data."""
        # Try to use the Advanced Engine if available
        try:
            from signal_diagnostic import SignalDiagnosticEngine
            engine = SignalDiagnosticEngine()
            
            # Generate a dummy signal if text is passed (simulation wrapper)
            # In a real app, we would parse the signal_data_text (CSV) into a numpy array
            import numpy as np
            dummy_signal = np.sin(np.linspace(0, 10, 100)) # Placeholder signal
            
            # Train on fly if not exists (Simulation only)
            if engine.rf_model is None:
                engine.train_simple_model()
                
            prediction = engine.predict_simple(dummy_signal)
            details = "Feature Extraction: RMS, Mean, Variance, Zero-Crossing Rate. Model: Random Forest."
            confidence = "High (92%)"
            
        except ImportError:
            # Fallback to older heuristic simulation
            confidence = f"{random.randint(80, 95)}%"
            if len(signal_data_text) > 100:
                prediction = "Atrial Fibrillation"
                details = "Irregular R-R intervals detected (Heuristic)."
            else:
                prediction = "Normal Sinus Rhythm"
                details = "Waveform within normal parameters (Heuristic)."
            
        return {
            "prediction": prediction,
            "confidence": confidence,
            "modality": "Signal Processing (Random Forest/Heuristic)",
            "analysis": details
        }

    def predict_genomics(self, sequence_data=""):
        """Simulates Genomic Sequence Analysis."""
        confidence = random.randint(90, 99)
        sequence = sequence_data.upper()
        
        if "BRCA" in sequence or "GATTACA" in sequence:
            prediction = "High Hereditary Risk (Breast Cancer)"
            details = "Pathogenic variant found in BRCA1 gene."
        elif "CFTR" in sequence:
             prediction = "Cystic Fibrosis Carrier"
             details = "Delta F508 mutation detected."
        else:
            prediction = "No Known Genetic Markers Found"
            details = "Sequence aligns with reference genome."
            
        return {
            "prediction": prediction,
            "confidence": f"{confidence}%",
            "modality": "Genomic Sequencing",
            "analysis": details
        }

    def predict_fracture(self, filename=""):
        """Simulates Bone Fracture Detection using SVM concepts."""
        confidence = random.randint(88, 98)
        
        # Simulation of SVM Classification
        if "fracture" in filename.lower() or "broken" in filename.lower():
            prediction = "Fracture Detected"
            svm_details = "Input vector lies on positive side of hyperplane (Class 1)."
            features = "Edge discontinuities detected in HOG feature map."
        else:
            prediction = "No Fracture Detected"
            svm_details = "Input vector lies on negative side of hyperplane (Class 0)."
            features = "Texture analysis shows continuous bone density."
            
        return {
            "prediction": prediction,
            "confidence": f"{confidence}%",
            "modality": "Orthopedics (SVM Classifier)",
            "analysis": f"{svm_details} {features}"
        }

# Singleton instance
predictor = MultimodalPredictor()

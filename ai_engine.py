"""
AI Health Companion - Multimodal Predictive Engine (Report Analysis Edition)
Integrates: S3, Rekognition, Comprehend Medical, Textract, Bedrock, DynamoDB, SNS
"""

import os
import json
import uuid
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MedTrack-AI")

# ─── AWS Region ────────────────────────────────────────────────────────────────
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
S3_BUCKET  = os.environ.get('AI_S3_BUCKET', 'medtrack-ai-inputs')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN',
    'arn:aws:sns:us-east-1:050690756868:Medtrack_cloud_enabled_healthcare_management')

# ─── Lazy AWS Clients ──────────────────────────────────────────────────────────
_clients = {}

def _get_client(service):
    if service not in _clients:
        try:
            import boto3
            _clients[service] = boto3.client(service, region_name=AWS_REGION)
        except Exception as e:
            logger.warning(f"Could not create {service} client: {e}")
            _clients[service] = None
    return _clients[service]

def _get_dynamo_table(table_name):
    try:
        import boto3
        dynamo = boto3.resource('dynamodb', region_name=AWS_REGION)
        return dynamo.Table(table_name)
    except Exception as e:
        logger.warning(f"Could not connect to DynamoDB table {table_name}: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. S3 – Upload medical image
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def upload_image_to_s3(file_obj, patient_id, filename):
    """Upload a file-like object to S3. Returns S3 key or None on failure."""
    s3 = _get_client('s3')
    if not s3:
        logger.info("[SIMULATION] S3 upload skipped – client unavailable")
        return f"simulated/{patient_id}/{filename}"

    key = f"{patient_id}/{filename}"
    try:
        s3.upload_fileobj(file_obj, S3_BUCKET, key,
                          ExtraArgs={'ServerSideEncryption': 'AES256'})
        logger.info(f"✅ S3 upload success: s3://{S3_BUCKET}/{key}")
        return key
    except Exception as e:
        logger.error(f"❌ S3 upload failed: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1b. S3 – Upload a lab/report file (PDF, JPEG, PNG)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def upload_report_to_s3(file_obj, patient_id, filename):
    """Upload a report file to S3 under reports/ prefix. Returns S3 key or None."""
    s3 = _get_client('s3')
    key = f"reports/{patient_id}/{filename}"
    if not s3:
        logger.info("[SIMULATION] S3 report upload skipped")
        return f"simulated/reports/{patient_id}/{filename}"
    try:
        s3.upload_fileobj(file_obj, S3_BUCKET, key,
                          ExtraArgs={'ServerSideEncryption': 'AES256'})
        logger.info(f"✅ S3 report upload: s3://{S3_BUCKET}/{key}")
        return key
    except Exception as e:
        logger.error(f"❌ S3 report upload failed: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2b. Amazon Textract – Extract text from lab reports / PDFs
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TEXTRACT_SIMULATION_REPORTS = {
    'blood': (
        "COMPLETE BLOOD COUNT REPORT\n"
        "WBC: 11.2 K/uL [HIGH]  RBC: 4.1 M/uL  Hemoglobin: 12.1 g/dL [LOW]\n"
        "Hematocrit: 37.2%  MCV: 80 fL  MCH: 28 pg  MCHC: 33 g/dL\n"
        "Platelets: 420 K/uL [HIGH]  Neutrophils: 74%  Lymphocytes: 18% [LOW]\n"
        "Interpretation: Leukocytosis with relative lymphopenia. "
        "Elevated platelets. Mild normocytic anemia. Consistent with bacterial infection or inflammatory process."
    ),
    'lipid': (
        "LIPID PANEL REPORT\n"
        "Total Cholesterol: 238 mg/dL [BORDERLINE HIGH]  LDL: 162 mg/dL [HIGH]\n"
        "HDL: 38 mg/dL [LOW]  Triglycerides: 190 mg/dL [BORDERLINE HIGH]\n"
        "VLDL: 38 mg/dL  LDL/HDL Ratio: 4.26 [HIGH RISK]\n"
        "Interpretation: Dyslipidemia with elevated LDL and low HDL. "
        "Cardiovascular risk elevated. Recommend dietary modification and statin therapy review."
    ),
    'thyroid': (
        "THYROID FUNCTION TESTS\n"
        "TSH: 0.18 mIU/L [LOW]  Free T4: 2.1 ng/dL [HIGH]  Free T3: 4.9 pg/mL\n"
        "Anti-TPO Antibodies: 142 IU/mL [POSITIVE]\n"
        "Interpretation: Suppressed TSH with elevated T4 indicates hyperthyroidism. "
        "Positive anti-TPO antibodies suggestive of Graves disease or autoimmune thyroiditis."
    ),
    'default': (
        "LABORATORY REPORT\n"
        "Glucose Fasting: 126 mg/dL [HIGH]  HbA1c: 7.2% [DIABETIC RANGE]\n"
        "Creatinine: 1.3 mg/dL [HIGH NORMAL]  eGFR: 68 mL/min/1.73m²\n"
        "Uric Acid: 8.1 mg/dL [HIGH]  ALT: 52 U/L [MILDLY ELEVATED]\n"
        "AST: 38 U/L  Albumin: 3.8 g/dL  Total Protein: 6.9 g/dL\n"
        "Interpretation: Elevated fasting glucose and HbA1c confirm diabetes mellitus. "
        "Mild renal impairment. Hyperuricemia noted. Liver enzymes mildly elevated."
    )
}


def classify_report_type(filename, text_hint=''):
    """Heuristically classify a report file into a known category."""
    combined = (filename + ' ' + text_hint).lower()
    if any(w in combined for w in ['blood', 'cbc', 'wbc', 'rbc', 'hemo', 'hemoglobin', 'platelet']):
        return 'blood'
    if any(w in combined for w in ['lipid', 'cholesterol', 'ldl', 'hdl', 'triglyceride']):
        return 'lipid'
    if any(w in combined for w in ['thyroid', 'tsh', 't3', 't4', 'thyroxine']):
        return 'thyroid'
    if any(w in combined for w in ['xray', 'x-ray', 'ct', 'scan', 'mri', 'xr']):
        return 'imaging'
    return 'default'


def analyze_report_with_textract(s3_key, filename='report.pdf'):
    """
    Use Amazon Textract to extract text from a medical report stored in S3.
    Falls back to realistic simulation when Textract is unavailable.
    Returns a structured dict with raw_text, lines, and a summary.
    """
    textract = _get_client('textract')
    report_type = classify_report_type(filename)

    if not textract or s3_key.startswith('simulated/'):
        sim_text = TEXTRACT_SIMULATION_REPORTS.get(report_type,
                                                    TEXTRACT_SIMULATION_REPORTS['default'])
        logger.info("[SIMULATION] Textract extraction simulated")
        return {
            'raw_text': sim_text,
            'lines': sim_text.split('\n'),
            'report_type': report_type,
            'word_count': len(sim_text.split()),
            'summary': sim_text[:280] + '…' if len(sim_text) > 280 else sim_text,
            'simulated': True
        }

    try:
        response = textract.detect_document_text(
            Document={'S3Object': {'Bucket': S3_BUCKET, 'Name': s3_key}}
        )
        blocks = response.get('Blocks', [])
        lines = [b['Text'] for b in blocks if b['BlockType'] == 'LINE']
        raw_text = '\n'.join(lines)
        logger.info(f"✅ Textract extracted {len(lines)} lines from {s3_key}")
        return {
            'raw_text': raw_text,
            'lines': lines,
            'report_type': classify_report_type(filename, raw_text[:500]),
            'word_count': len(raw_text.split()),
            'summary': raw_text[:280] + '…' if len(raw_text) > 280 else raw_text,
            'simulated': False
        }
    except Exception as e:
        logger.error(f"❌ Textract error: {e}")
        sim_text = TEXTRACT_SIMULATION_REPORTS.get(report_type,
                                                    TEXTRACT_SIMULATION_REPORTS['default'])
        return {
            'raw_text': sim_text,
            'lines': sim_text.split('\n'),
            'report_type': report_type,
            'word_count': len(sim_text.split()),
            'summary': sim_text[:280] + '…',
            'simulated': True
        }


def extract_report_insights(textract_result, text_entities):
    """
    Cross-reference Textract output with Comprehend Medical entities
    to produce structured report insights.
    """
    raw = textract_result.get('raw_text', '')
    report_type = textract_result.get('report_type', 'default')
    lines = textract_result.get('lines', [])

    # Pick out abnormal markers by keywords
    abnormal_markers = []
    for line in lines:
        upper = line.upper()
        if any(tag in upper for tag in ['HIGH', 'LOW', 'ELEVATED', 'CRITICAL',
                                         'ABNORMAL', 'POSITIVE', 'REACTIVE',
                                         'OUT OF RANGE', 'H]', 'L]']):
            abnormal_markers.append(line.strip())

    entities = text_entities.get('entities', [])
    conditions_found = [e['Text'] for e in entities
                        if e.get('Category') in ('MEDICAL_CONDITION', 'DX_NAME')][:6]
    medications_found = [e['Text'] for e in entities
                         if e.get('Category') == 'MEDICATION'][:4]

    type_labels = {
        'blood':   'Complete Blood Count (CBC)',
        'lipid':   'Lipid / Cardiovascular Panel',
        'thyroid': 'Thyroid Function Tests',
        'imaging': 'Medical Imaging Report',
        'default': 'General Laboratory Report'
    }

    return {
        'report_label':     type_labels.get(report_type, 'Laboratory Report'),
        'report_type':      report_type,
        'abnormal_markers': abnormal_markers[:8],
        'conditions_found': conditions_found,
        'medications_found': medications_found,
        'total_lines':      len(lines),
        'word_count':       textract_result.get('word_count', 0),
        'key_excerpt':      '\n'.join(lines[:6]) if lines else raw[:300],
        'full_text':        raw
    }


def analyze_multiple_reports(report_files, patient_id):
    """
    Process a list of report files (werkzeug FileStorage objects).
    Returns a list of per-report analysis dicts.
    """
    results = []
    for f in (report_files or []):
        if not f or getattr(f, 'filename', '') == '':
            continue
        safe_name = f.filename.replace(' ', '_')
        s3_key = upload_report_to_s3(f.stream, patient_id, safe_name)
        textract_result = analyze_report_with_textract(s3_key or '', safe_name)
        symptom_text = textract_result.get('raw_text', '')
        text_entities = extract_medical_entities(symptom_text[:5000])
        insights = extract_report_insights(textract_result, text_entities)
        results.append({
            'filename':   safe_name,
            's3_key':     s3_key,
            'textract':   textract_result,
            'entities':   text_entities,
            'insights':   insights,
        })
    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Master Pipeline – Report Analysis Mode
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def run_report_analysis_pipeline(patient_data, report_files):
    """
    Dedicated pipeline for multimodal REPORT analysis:
    1. Upload each report to S3
    2. Extract text with Textract
    3. Identify medical entities (Comprehend Medical)
    4. Synthesize insights
    5. Generate final prediction via Bedrock using extracted text
    6. Persist to DynamoDB & trigger SNS if needed
    Returns: full analysis dict
    """
    pid = patient_data.get('patient_id', str(uuid.uuid4())[:8])
    report_analyses = analyze_multiple_reports(report_files, pid)

    # Combine all extracted text for Bedrock context
    combined_text = '\n\n'.join(
        r['textract'].get('raw_text', '') for r in report_analyses
    ) or patient_data.get('symptoms', '')

    # Enrich patient_data symptoms with report text
    enriched_data = dict(patient_data)
    if combined_text:
        existing = enriched_data.get('symptoms', '')
        enriched_data['symptoms'] = (
            existing + '\n\n[EXTRACTED FROM REPORTS]\n' + combined_text[:8000]
            if existing else combined_text[:8000]
        )

    # Extract medical entities from the full combined text
    text_findings = extract_medical_entities(combined_text[:20000])

    # Aggregate abnormal markers across all reports
    all_abnormal = []
    for r in report_analyses:
        all_abnormal.extend(r['insights'].get('abnormal_markers', []))

    # Image finding stub (no imaging in this mode)
    image_findings = {
        'summary': (
            f"Multimodal Report Analysis: {len(report_analyses)} report(s) uploaded. "
            f"{len(all_abnormal)} abnormal marker(s) detected across reports."
        ),
        'simulated': any(r['textract'].get('simulated') for r in report_analyses)
    }

    # Generate Bedrock prediction
    prediction = generate_prediction_with_bedrock(enriched_data, image_findings, text_findings)

    # Embed report analysis results into prediction
    prediction['report_analyses'] = report_analyses
    prediction['report_abnormal_markers'] = all_abnormal[:10]
    prediction['report_count'] = len(report_analyses)
    prediction['pipeline_mode'] = 'report_analysis'

    # Confidence warning
    try:
        conf_val = float(prediction.get('confidence_score', '0%').replace('%', ''))
        prediction['low_confidence_warning'] = conf_val < 75
    except Exception:
        prediction['low_confidence_warning'] = False

    # Persist & alert
    save_prediction_to_dynamodb(prediction)
    send_sns_alert(prediction)

    return prediction


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Rekognition – Analyse medical image for labels / anomalies
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def analyze_image_with_rekognition(s3_key):
    """Return a dict of findings from Rekognition detect_labels."""
    rek = _get_client('rekognition')
    if not rek or s3_key.startswith('simulated/'):
        return {
            "labels": [
                {"Name": "Medical Imaging", "Confidence": 97.4},
                {"Name": "X-Ray", "Confidence": 93.1},
                {"Name": "Lung", "Confidence": 88.6},
            ],
            "summary": "Simulated: Radiological image detected with potential density irregularities.",
            "simulated": True
        }

    try:
        response = rek.detect_labels(
            Image={'S3Object': {'Bucket': S3_BUCKET, 'Name': s3_key}},
            MaxLabels=20,
            MinConfidence=60
        )
        labels = response.get('Labels', [])
        label_names = [l['Name'] for l in labels[:5]]
        return {
            "labels": labels,
            "summary": f"Image contains: {', '.join(label_names)}.",
            "simulated": False
        }
    except Exception as e:
        logger.error(f"❌ Rekognition error: {e}")
        return {"labels": [], "summary": f"Image analysis unavailable: {e}", "simulated": True}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Comprehend Medical – Extract clinical entities from symptom text
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def extract_medical_entities(symptom_text):
    """Return extracted entities from Amazon Comprehend Medical."""
    cm = _get_client('comprehendmedical')
    if not cm or not symptom_text:
        # Simulation
        return {
            "entities": [
                {"Text": "chest pain", "Category": "SYMPTOM", "Score": 0.96},
                {"Text": "shortness of breath", "Category": "SYMPTOM", "Score": 0.94},
                {"Text": "hypertension", "Category": "MEDICAL_CONDITION", "Score": 0.91},
            ],
            "summary": "Clinical entities extracted (simulated): chest pain, shortness of breath, hypertension.",
            "simulated": True
        }

    try:
        response = cm.detect_entities_v2(Text=symptom_text[:20000])
        entities = response.get('Entities', [])
        texts = [e['Text'] for e in entities[:8]]
        return {
            "entities": entities,
            "summary": f"Clinical entities: {', '.join(texts)}." if texts else "No specific entities detected.",
            "simulated": False
        }
    except Exception as e:
        logger.error(f"❌ Comprehend Medical error: {e}")
        return {"entities": [], "summary": f"Text analysis unavailable: {e}", "simulated": True}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. Amazon Bedrock – Generate AI reasoning & structured prediction report
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def generate_prediction_with_bedrock(patient_data, image_findings, text_findings):
    """
    Call Amazon Bedrock (Claude) to produce a structured prediction JSON.
    Falls back to a deterministic simulation when Bedrock is unavailable.
    """
    bedrock = _get_client('bedrock-runtime')

    # Build the prompt
    vitals_str = (
        f"BP: {patient_data.get('bp', 'N/A')}, "
        f"SpO2: {patient_data.get('spo2', 'N/A')}%, "
        f"HbA1c: {patient_data.get('hba1c', 'N/A')}%, "
        f"WBC: {patient_data.get('wbc', 'N/A')} K/uL, "
        f"Cholesterol: {patient_data.get('cholesterol', 'N/A')} mg/dL"
    )

    prompt = f"""You are an expert clinical AI assistant. Analyze the following patient data and produce a structured health prediction report in valid JSON format matching the schema exactly.

Patient Information:
- Patient ID: {patient_data.get('patient_id', 'UNKNOWN')}
- Age: {patient_data.get('age', 'N/A')}
- Gender: {patient_data.get('gender', 'N/A')}
- Reported Symptoms: {patient_data.get('symptoms', 'None')}
- Doctor Notes: {patient_data.get('doctor_notes', 'None')}

Vitals:
{vitals_str}

Image Analysis (Rekognition):
{image_findings}

Symptom Text Analysis (Comprehend Medical):
{text_findings}

Produce ONLY valid JSON in this exact format (no markdown, no explanation):
{{
  "patient_id": "{patient_data.get('patient_id', '')}",
  "timestamp": "{datetime.now(timezone.utc).isoformat()}",
  "confidence_score": "82%",
  "primary_prediction": {{
    "condition": "Hypertensive Heart Disease",
    "severity": "High",
    "probability": "78%",
    "icd_10_code": "I11.9"
  }},
  "differential_diagnoses": [
    {{"condition": "Coronary Artery Disease", "probability": "45%"}},
    {{"condition": "Pulmonary Hypertension", "probability": "30%"}}
  ],
  "modality_insights": {{
    "image_findings": "describe what was found in the image",
    "text_findings": "describe what was found in symptom text",
    "vitals_analysis": "describe the vitals interpretation"
  }},
  "risk_flags": ["Elevated BP detected", "SpO2 below threshold"],
  "recommended_actions": {{
    "immediate": "Immediate action",
    "short_term": "Short term plan",
    "long_term": "Long term plan",
    "specialist_referral": "Cardiologist"
  }},
  "alert_trigger": {{
    "send_alert": true,
    "priority": "High",
    "message": "Patient requires immediate attention"
  }},
  "explainability": {{
    "key_factors": ["High BP", "Elevated WBC", "Chest pain symptom"],
    "reasoning": "Clinical reasoning based on combined multimodal data",
    "data_gaps": "Echocardiogram not provided"
  }}
}}"""

    if bedrock:
        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}]
            })
            response = bedrock.invoke_model(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            result_body = json.loads(response['body'].read())
            raw_text = result_body['content'][0]['text']
            prediction = json.loads(raw_text)
            prediction['_source'] = 'bedrock'
            logger.info("✅ Bedrock prediction generated successfully")
            return prediction
        except Exception as e:
            logger.error(f"❌ Bedrock error: {e}")

    # ── Deterministic Simulation ──────────────────────────────────────────────
    logger.info("[SIMULATION] Generating deterministic fallback prediction")
    return _build_simulated_prediction(patient_data, image_findings, text_findings, vitals_str)


def _build_simulated_prediction(patient_data, image_findings, text_findings, vitals_str):
    """Rule-based simulation when Bedrock is unavailable."""
    pid     = patient_data.get('patient_id', 'UNKNOWN')
    age     = int(patient_data.get('age', 40) or 40)
    symptoms = (patient_data.get('symptoms') or '').lower()

    # Determine severity from vitals
    try:
        bp_sys = int((patient_data.get('bp') or '120/80').split('/')[0])
    except Exception:
        bp_sys = 120

    try:
        spo2 = float(patient_data.get('spo2') or 98)
    except Exception:
        spo2 = 98

    try:
        hba1c = float(patient_data.get('hba1c') or 5.5)
    except Exception:
        hba1c = 5.5

    try:
        chol = float(patient_data.get('cholesterol') or 180)
    except Exception:
        chol = 180

    risk_flags = []
    severity   = 'Low'
    condition  = 'General Health Screening – No Specific Pathology Detected'
    icd        = 'Z00.00'
    prob       = '72%'
    conf       = '81%'

    if bp_sys >= 180:
        risk_flags.append("Hypertensive Crisis (BP ≥ 180 mmHg)")
        severity = 'Critical'
    elif bp_sys >= 140:
        risk_flags.append("Stage 2 Hypertension (BP ≥ 140 mmHg)")
        severity = 'High'
    elif bp_sys >= 130:
        risk_flags.append("Stage 1 Hypertension (BP ≥ 130 mmHg)")
        if severity == 'Low':
            severity = 'Moderate'

    if spo2 < 90:
        risk_flags.append("Critical Hypoxemia (SpO2 < 90%)")
        severity = 'Critical'
    elif spo2 < 95:
        risk_flags.append("Low Oxygen Saturation (SpO2 < 95%)")
        if severity in ('Low', 'Moderate'):
            severity = 'High'

    if hba1c >= 10:
        risk_flags.append("Poorly Controlled Diabetes (HbA1c ≥ 10%)")
        if severity == 'Low':
            severity = 'High'
    elif hba1c >= 6.5:
        risk_flags.append("Diabetic Range HbA1c (≥ 6.5%)")
        if severity == 'Low':
            severity = 'Moderate'

    if chol >= 240:
        risk_flags.append("High Cholesterol (≥ 240 mg/dL)")
        if severity == 'Low':
            severity = 'Moderate'

    if age >= 65:
        risk_flags.append("Geriatric Patient – Elevated Baseline Risk")

    # Symptom-based refinement
    if 'chest' in symptoms or 'heart' in symptoms:
        condition = 'Suspected Cardiac Event / Angina Pectoris'
        icd = 'I20.9'
        prob = '76%'
        if severity == 'Low':
            severity = 'Moderate'
    elif 'breath' in symptoms or 'respiratory' in symptoms or 'cough' in symptoms:
        condition = 'Respiratory Distress – Possible COPD / Asthma'
        icd = 'J44.1'
        prob = '74%'
    elif 'headache' in symptoms or 'dizziness' in symptoms:
        condition = 'Neurological: Migraine / Hypertensive Headache'
        icd = 'G43.909'
        prob = '70%'
    elif 'diabetes' in symptoms or 'sugar' in symptoms or 'glucose' in symptoms:
        condition = 'Type 2 Diabetes Mellitus – Metabolic Syndrome Risk'
        icd = 'E11.9'
        prob = '78%'

    if not risk_flags:
        risk_flags.append("No critical risk flags identified")

    send_alert = severity in ('High', 'Critical')

    return {
        "patient_id": pid,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "confidence_score": conf,
        "primary_prediction": {
            "condition": condition,
            "severity": severity,
            "probability": prob,
            "icd_10_code": icd
        },
        "differential_diagnoses": [
            {"condition": "Metabolic Syndrome", "probability": "38%"},
            {"condition": "Anxiety / Stress-Related Disorder", "probability": "22%"}
        ],
        "modality_insights": {
            "image_findings": image_findings if isinstance(image_findings, str) else image_findings.get('summary', 'No image provided'),
            "text_findings": text_findings if isinstance(text_findings, str) else text_findings.get('summary', 'No symptoms text provided'),
            "vitals_analysis": (
                f"Vitals reviewed: {vitals_str}. "
                f"{'BP is elevated. ' if bp_sys >= 130 else 'BP within range. '}"
                f"{'SpO2 below safe threshold. ' if spo2 < 95 else 'SpO2 acceptable. '}"
                f"{'HbA1c indicates diabetic risk. ' if hba1c >= 6.5 else ''}"
                f"{'Cholesterol is high. ' if chol >= 200 else ''}"
            )
        },
        "risk_flags": risk_flags,
        "recommended_actions": {
            "immediate": "Monitor vitals every 4 hours; notify attending physician." if severity in ('High', 'Critical') else "Routine monitoring.",
            "short_term": "Schedule follow-up within 48–72 hours with specialist." if severity != 'Low' else "Schedule routine checkup in 30 days.",
            "long_term": "Implement lifestyle modifications: DASH diet, regular aerobic exercise, smoking cessation.",
            "specialist_referral": (
                "Cardiologist" if ('cardiac' in condition.lower() or bp_sys >= 140)
                else "Pulmonologist" if 'respiratory' in condition.lower()
                else "Endocrinologist" if 'diabetes' in condition.lower() or hba1c >= 6.5
                else "General Practitioner"
            )
        },
        "alert_trigger": {
            "send_alert": send_alert,
            "priority": severity if send_alert else "Low",
            "message": (
                f"URGENT: Patient {pid} – {severity} severity prediction for '{condition}'. "
                f"Immediate clinical review required."
            ) if send_alert else f"Routine AI prediction for patient {pid}."
        },
        "explainability": {
            "key_factors": risk_flags[:3] if risk_flags else ["No critical factors"],
            "reasoning": (
                f"Combined analysis of vitals ({vitals_str}), "
                f"symptom text entities, and medical imaging produced this prediction. "
                f"The model weighted BP, SpO2, HbA1c and clinical symptom entities."
            ),
            "data_gaps": "Full ECG, complete blood count, and radiologist report not available."
        },
        "_source": "simulation"
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. DynamoDB – Persist prediction result
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def save_prediction_to_dynamodb(prediction):
    """Store the prediction JSON in MedTrack_Predictions table."""
    table = _get_dynamo_table('MedTrack_Predictions')
    if not table:
        logger.info("[SIMULATION] DynamoDB save skipped – table unavailable")
        return True

    try:
        import decimal
        item = {
            'patient_id':       prediction.get('patient_id', 'UNKNOWN'),
            'timestamp':        prediction.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'condition':        prediction.get('primary_prediction', {}).get('condition', ''),
            'severity':         prediction.get('primary_prediction', {}).get('severity', ''),
            'confidence_score': prediction.get('confidence_score', ''),
            'risk_flags':       json.dumps(prediction.get('risk_flags', [])),
            'recommended_actions': json.dumps(prediction.get('recommended_actions', {})),
            'alert_sent':       str(prediction.get('alert_trigger', {}).get('send_alert', False)),
            'full_report':      json.dumps(prediction)
        }
        table.put_item(Item=item)
        logger.info(f"✅ Prediction saved to DynamoDB for patient {item['patient_id']}")
        return True
    except Exception as e:
        logger.error(f"❌ DynamoDB save error: {e}")
        return False


def get_high_risk_predictions(limit=50):
    """Fetch High/Critical predictions for doctor alert dashboard."""
    table = _get_dynamo_table('MedTrack_Predictions')
    if not table:
        # Return demo data for display
        return _demo_alert_data()

    try:
        response = table.scan(
            FilterExpression='severity IN (:h, :c)',
            ExpressionAttributeValues={':h': 'High', ':c': 'Critical'}
        )
        items = response.get('Items', [])
        items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return items[:limit]
    except Exception as e:
        logger.error(f"❌ DynamoDB scan error: {e}")
        return _demo_alert_data()


def get_prediction_by_id(patient_id, timestamp):
    """Fetch a single prediction record."""
    table = _get_dynamo_table('MedTrack_Predictions')
    if not table:
        return None
    try:
        response = table.get_item(Key={'patient_id': patient_id, 'timestamp': timestamp})
        return response.get('Item')
    except Exception as e:
        logger.error(f"❌ DynamoDB get_item error: {e}")
        return None


def _demo_alert_data():
    return [
        {
            'patient_id': 'PT-001',
            'condition': 'Suspected Cardiac Event / Angina Pectoris',
            'severity': 'Critical',
            'confidence_score': '89%',
            'timestamp': '2026-02-26T10:30:00+00:00',
            'alert_sent': 'True'
        },
        {
            'patient_id': 'PT-042',
            'condition': 'Hypertensive Heart Disease',
            'severity': 'High',
            'confidence_score': '82%',
            'timestamp': '2026-02-26T09:15:00+00:00',
            'alert_sent': 'True'
        },
        {
            'patient_id': 'PT-017',
            'condition': 'Respiratory Distress – Possible COPD',
            'severity': 'High',
            'confidence_score': '77%',
            'timestamp': '2026-02-25T22:45:00+00:00',
            'alert_sent': 'True'
        }
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. SNS – Send alert for High / Critical predictions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def send_sns_alert(prediction):
    """Publish an SNS alert when severity is High or Critical."""
    alert = prediction.get('alert_trigger', {})
    if not alert.get('send_alert'):
        return False

    priority = alert.get('priority', 'High')
    message  = alert.get('message', '')
    subject  = f"🚨 MedTrack AI Alert – {priority} Priority"

    full_msg = f"""{message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Patient ID   : {prediction.get('patient_id')}
Condition    : {prediction.get('primary_prediction', {}).get('condition')}
Severity     : {prediction.get('primary_prediction', {}).get('severity')}
ICD-10 Code  : {prediction.get('primary_prediction', {}).get('icd_10_code')}
Confidence   : {prediction.get('confidence_score')}
Timestamp    : {prediction.get('timestamp')}

Risk Flags:
{chr(10).join('• ' + f for f in prediction.get('risk_flags', []))}

Recommended Immediate Action:
{prediction.get('recommended_actions', {}).get('immediate', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is an automated AI Health Companion alert.
AI recommendations are assistive only – doctor has final say.
"""

    sns = _get_client('sns')
    if sns:
        try:
            response = sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=full_msg,
                Subject=subject
            )
            logger.info(f"✅ SNS Alert sent: {response.get('MessageId')}")
            return True
        except Exception as e:
            logger.error(f"❌ SNS publish error: {e}")

    # Simulation fallback
    logger.info(f"[SIMULATION] SNS Alert\nSubject: {subject}\n{full_msg}")
    return True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. Master Pipeline Orchestrator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def run_ai_pipeline(patient_data, image_file=None, report_files=None):
    """
    Full AI pipeline:
    1. Upload image to S3 (if provided)
    2. Analyse image with Rekognition
    3. Upload & analyse report files with Textract (if provided)
    4. Extract medical entities from symptoms text (Comprehend Medical)
    5. Generate prediction with Bedrock
    6. Save results to DynamoDB
    7. Trigger SNS if High/Critical
    Returns: prediction dict
    """
    pid = patient_data.get('patient_id', str(uuid.uuid4())[:8])

    # Step 1 & 2 – Image
    image_findings = {"summary": "No medical image provided.", "simulated": True}
    s3_key = None
    if image_file and getattr(image_file, 'filename', '') != '':
        safe_name = image_file.filename.replace(' ', '_')
        s3_key = upload_image_to_s3(image_file.stream, pid, safe_name)
        if s3_key:
            image_findings = analyze_image_with_rekognition(s3_key)

    # Step 2b – Report files (Textract)
    report_analyses = []
    if report_files:
        actual_reports = [f for f in (report_files if isinstance(report_files, list) else [report_files])
                          if f and getattr(f, 'filename', '') != '']
        if actual_reports:
            report_analyses = analyze_multiple_reports(actual_reports, pid)
            # Inject extracted report text into symptoms for better Bedrock context
            combined_report_text = '\n\n'.join(
                r['textract'].get('raw_text', '') for r in report_analyses
            )
            if combined_report_text:
                existing_symptoms = patient_data.get('symptoms', '')
                patient_data = dict(patient_data)
                patient_data['symptoms'] = (
                    existing_symptoms + '\n\n[REPORT EXTRACTS]\n' + combined_report_text[:6000]
                    if existing_symptoms else combined_report_text[:6000]
                )

    # Step 3 – Text
    symptoms_text = patient_data.get('symptoms', '')
    text_findings = extract_medical_entities(symptoms_text[:20000])

    # Step 4 – Bedrock Prediction
    prediction = generate_prediction_with_bedrock(patient_data, image_findings, text_findings)

    # Attach S3 key for reference
    if s3_key:
        prediction['s3_image_key'] = s3_key

    # Attach report analysis results
    if report_analyses:
        prediction['report_analyses'] = report_analyses
        prediction['report_count'] = len(report_analyses)
        all_abnormal = []
        for r in report_analyses:
            all_abnormal.extend(r['insights'].get('abnormal_markers', []))
        prediction['report_abnormal_markers'] = all_abnormal[:10]

    # Attach low-confidence warning flag
    try:
        conf_val = float(prediction.get('confidence_score', '0%').replace('%', ''))
        prediction['low_confidence_warning'] = conf_val < 75
    except Exception:
        prediction['low_confidence_warning'] = False

    # Step 5 – Persist to DynamoDB
    save_prediction_to_dynamodb(prediction)

    # Step 6 – SNS Alert
    send_sns_alert(prediction)

    return prediction

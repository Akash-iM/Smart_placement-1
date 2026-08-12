import math

def predict_placement(cgpa, skills_text, ats_score=None):
    """
    Simulated ML Logistic Regression classifier to predict Placement Probability.
    Based on CGPA (0-10), Skills Count, and ATS Resume formatting score (0-100).
    """
    w_cgpa = 0.8
    w_skills = 0.4
    w_ats = 0.05
    bias = -9.5
    
    # Process inputs
    cgpa_val = float(cgpa) if cgpa else 0.0
    skills_count = len([s for s in str(skills_text).split(',') if s.strip()]) if skills_text else 0
    ats_val = float(ats_score) if ats_score else 0.0
    
    # Calculate Z (weighted sum)
    z = bias + (w_cgpa * cgpa_val) + (w_skills * skills_count) + (w_ats * ats_val)
    
    # Sigmoid Activation Function
    probability = 1 / (1 + math.exp(-z))
    
    return round(probability * 100)

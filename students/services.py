import re

def analyze_resume(student_skills, job_skills):
    """
    Very basic skill matching logic returning a percentage.
    """
    if not job_skills:
        return 100
    
    st_skills = [s.strip().lower() for s in student_skills.split(',') if s.strip()]
    req_skills = [s.strip().lower() for s in job_skills.split(',') if s.strip()]
    
    if not req_skills:
        return 100
        
    matches = sum(1 for skill in req_skills if any(skill in s or s in skill for s in st_skills))
    
    match_percentage = int((matches / len(req_skills)) * 100)
    return min(match_percentage, 100)

def evaluate_interview(question, answer):
    """
    Simulated AI evaluation for mock interview answers.
    Returns: feedback string, score (0-10)
    """
    if not answer or len(answer.strip()) < 10:
        return "Your answer is too short. Please provide more detail using the STAR method.", 3
        
    # Basic heuristic scoring
    score_base = 5
    length_bonus = min(len(answer.split()) // 20, 3) # max +3 for length
    
    # Keyword bonus
    keywords = ['because', 'example', 'result', 'learned', 'team', 'first', 'ensure']
    kw_bonus = min(sum(1 for k in keywords if k in answer.lower()), 2)
    
    score = min(score_base + length_bonus + kw_bonus, 10)
    
    feedback = "Good response."
    if score >= 8:
        feedback = "Excellent answer. You provided good context and structure."
    elif score >= 6:
        feedback = "Good attempt, but try to structure your answer more clearly with specific outcomes."
        
    return feedback, score

def calculate_composite_score(student):
    """
    Combines CGPA (scaled to 100) and interview scores to determine a final AI readiness score.
    """
    cgpa_score = float(student.cgpa) * 10
    
    interviews = student.interviews.all()
    if interviews.exists():
        int_scores = [i.score for i in interviews if i.score is not None]
        avg_int = sum(int_scores) / len(int_scores) if int_scores else 0
        int_score = avg_int * 10 
    else:
        int_score = cgpa_score 
        
    final_score = (cgpa_score * 0.4) + (int_score * 0.6)
    return int(final_score)

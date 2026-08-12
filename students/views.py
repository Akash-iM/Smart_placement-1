import json

from django.conf import settings
from django.db.models import Count, Avg
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group

from .models import Student, MockInterviewQuestion, MockInterviewSession, MockInterviewMessage
from .forms import StudentForm
from django.core.paginator import Paginator

from rest_framework import generics, permissions
from .serializers import (
    StudentSerializer,
    MockInterviewQuestionSerializer,
    MockInterviewSessionSerializer,
)

try:
    import openai
except ImportError:
    openai = None


def role_required(*roles):
    def decorator(fn):
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser:
                return fn(request, *args, **kwargs)
            if hasattr(request.user, 'profile') and request.user.profile.role in roles:
                return fn(request, *args, **kwargs)
            return HttpResponseForbidden('You do not have permission to view this page.')
        return wrapper
    return decorator

@role_required('coordinator', 'recruiter')
def student_list(request):
    q = request.GET.get('q', '')
    students = Student.objects.filter(name__icontains=q).order_by('name')

    total_students = Student.objects.count()
    top_student = Student.objects.order_by('-cgpa').first()
    top_cgpa = top_student.cgpa if top_student else 0.0

    paginator = Paginator(students, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'students/students.html', {
        'students': page_obj, 
        'q': q, 
        'page_obj': page_obj,
        'total_students': total_students,
        'top_cgpa': top_cgpa
    })


@role_required('coordinator', 'recruiter')
def add_student(request):
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Student created successfully.')
            return redirect('students:student_list')
    else:
        form = StudentForm()

    return render(request, 'students/add_student.html', {'form': form})


@role_required('coordinator', 'recruiter')
def edit_student(request, id):
    student = get_object_or_404(Student, id=id)
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, 'Student updated successfully.')
            return redirect('students:student_list')
    else:
        form = StudentForm(instance=student)

    return render(request, 'students/edit_student.html', {'form': form, 'student': student})


@role_required('coordinator', 'recruiter')
def delete_student(request, id):
    student = get_object_or_404(Student, id=id)
    if request.method == 'POST':
        student.delete()
        messages.success(request, 'Student deleted successfully.')
        return redirect('students:student_list')

    return render(request, 'students/delete_student.html', {'student': student})


def api_docs(request):
    return render(request, 'api_docs.html', {
        'base_url': request.build_absolute_uri('/')[:-1],
    })


def mock_interview(request):
    # load top 20 sample questions in bank, create defaults if missing
    if MockInterviewQuestion.objects.count() < 10:
        default_questions = [
            'Tell me about yourself.',
            'What are your strengths?',
            'What are your weaknesses?',
            'Why do you want to work here?',
            'Describe a challenge you faced and how you overcame it.',
            'Where do you see yourself in five years?',
            'Why should we hire you?',
            'How do you handle tight deadlines?',
            'Describe a successful team project.',
            'What are your salary expectations?'
        ]
        for q in default_questions:
            MockInterviewQuestion.objects.get_or_create(text=q)

    question_bank = MockInterviewQuestion.objects.order_by('id')[:20]
    sessions = MockInterviewSession.objects.order_by('-created_at')[:10]
    return render(request, 'students/mock_interview.html', {'question_bank': question_bank, 'sessions': sessions})


def _ai_mock_response(query):
    prompt = query.strip()
    if not prompt:
        return 'Please ask a question about mock interviews or career advice.', None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=getattr(settings, 'OPENAI_API_KEY', ''))
        
        system_msg = (
            "You are an expert technical interviewer and career coach. "
            "If the user asks an interview preparation question, provide a concise, professional answer. "
            "If the user is answering an interview question (e.g., they provide a response to a common question), "
            "evaluate their answer, provide constructive feedback, and give a score from 0 to 10. "
            "Always return your response in strictly valid JSON format with two keys: "
            "'answer' (string: containing your response or feedback) and "
            "'score' (integer 0-10, or null if a score is not applicable)."
        )
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ]
        )
        content = completion.choices[0].message.content
        data = json.loads(content)
        return data.get('answer', 'I received your message.'), data.get('score')
    except Exception as e:
        q = prompt.lower()
        if 'hello' in q or 'hi' in q:
            return 'Hello! I am your interview coach. Tell me what role you are preparing for.', None
        if 'strength' in q:
            return 'Mention a real strength with an example, such as problem solving or teamwork.', None
        if 'weakness' in q:
            return 'Choose a real weakness and explain how you are improving it.', None
        if 'tell me about yourself' in q:
            return 'Summarize your background in 30 seconds: education, projects, and what you want to do next.', None
        if 'why do you want' in q or 'why should we hire' in q:
            return 'Connect your skills to the role, mention your passion, and explain how you add value.', None
        if 'ready' in q and 'interview' in q:
            return 'Great! Start with a strong intro, maintain eye contact, and answer with STAR structure.', None
        if 'bye' in q or 'thank' in q:
            return 'You are welcome! Practice the answers again and good luck on your mock interview.', None

        return 'That is a good question. Frame the answer with context, action, and result (STAR pattern).', None


@csrf_exempt
def mock_interview_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid JSON payload'}, status=400)

    question = payload.get('question', '').strip()
    session_id = payload.get('session_id')
    question_id = payload.get('question_id')

    if not question:
        return JsonResponse({'error': 'Question is required.'}, status=400)

    # create or continue session
    if session_id:
        session = MockInterviewSession.objects.filter(id=session_id).first()
    else:
        student_profile = None
        if request.user.is_authenticated:
            student_profile = Student.objects.filter(user=request.user).first()
        session = MockInterviewSession.objects.create(student=student_profile)

    user_message = MockInterviewMessage.objects.create(session=session, sender='user', text=question)

    # store asked question if from question bank
    if question_id:
        selected_question = MockInterviewQuestion.objects.filter(id=question_id).first()
        if selected_question:
            question = selected_question.text

    try:
        answer, score = _ai_mock_response(question)
    except Exception as e:
        return JsonResponse({'error': f'Failed to generate response: {str(e)}'}, status=500)

    bot_message = MockInterviewMessage.objects.create(session=session, sender='bot', text=answer, score=score)

    session.updated_at = bot_message.created_at
    session.save()

    return JsonResponse({'session_id': session.id, 'question': question, 'answer': answer, 'score': score})


def analytics_dashboard(request):
    total_students = Student.objects.count()
    total_sessions = MockInterviewSession.objects.count()
    total_questions = MockInterviewQuestion.objects.count()
    latest_session = MockInterviewSession.objects.order_by('-updated_at').first()

    branch_stats = list(
        Student.objects.values('branch')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    cgpa_bins = {
        '0-5': 0, '5-6': 0, '6-7': 0, '7-8': 0, '8-9': 0, '9-10': 0,
    }
    for s in Student.objects.all():
        cgpa = float(s.cgpa)
        if cgpa < 5: cgpa_bins['0-5'] += 1
        elif cgpa < 6: cgpa_bins['5-6'] += 1
        elif cgpa < 7: cgpa_bins['6-7'] += 1
        elif cgpa < 8: cgpa_bins['7-8'] += 1
        elif cgpa < 9: cgpa_bins['8-9'] += 1
        else: cgpa_bins['9-10'] += 1

    days = 30
    window_start = timezone.now().date() - timedelta(days=days)
    offers_last_n = Student.objects.filter(offer_date__gte=window_start)
    offer_rate = round(offers_last_n.count() / total_students * 100, 2) if total_students > 0 else 0

    skill_freq = {}
    for s in Student.objects.exclude(skills='').values_list('skills', flat=True):
        for skill in [x.strip().lower() for x in s.split(',') if x.strip()]:
            skill_freq[skill] = skill_freq.get(skill, 0) + 1

    sorted_skills = sorted(skill_freq.items(), key=lambda kv: kv[1], reverse=True)
    top_skills = [{'skill': skill, 'count': cnt, 'pf': round(cnt / total_students * 100, 1)} for skill, cnt in sorted_skills[:5]]
    top_students = list(Student.objects.order_by('-cgpa')[:5])

    # Placement Analytics 
    placements_by_branch = list(
        Student.objects.filter(applications__status='Selected').distinct()
        .values('branch')
        .annotate(count=Count('id'))
    )
    
    application_stats = list(
        Application.objects.values('status')
        .annotate(count=Count('id'))
    )

    return render(request, 'dashboards/analytics_dashboard.html', {
        'total_students': total_students,
        'total_sessions': total_sessions,
        'total_questions': total_questions,
        'latest_session': latest_session,
        'branch_stats': branch_stats,
        'cgpa_bins': cgpa_bins,
        'offer_rate': offer_rate,
        'offer_window': days,
        'top_skills': top_skills,
        'top_students': top_students,
        'placements_by_branch': placements_by_branch,
        'application_stats': application_stats,
    })

def home(request):
    total_students = Student.objects.count()
    total_sessions = MockInterviewSession.objects.count()
    total_questions = MockInterviewQuestion.objects.count()
    latest_session = MockInterviewSession.objects.order_by('-updated_at').first()

    branch_stats = list(
        Student.objects.values('branch')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    cgpa_bins = {
        '0-5': 0,
        '5-6': 0,
        '6-7': 0,
        '7-8': 0,
        '8-9': 0,
        '9-10': 0,
    }
    for s in Student.objects.all():
        cgpa = float(s.cgpa)
        if cgpa < 5:
            cgpa_bins['0-5'] += 1
        elif cgpa < 6:
            cgpa_bins['5-6'] += 1
        elif cgpa < 7:
            cgpa_bins['6-7'] += 1
        elif cgpa < 8:
            cgpa_bins['7-8'] += 1
        elif cgpa < 9:
            cgpa_bins['8-9'] += 1
        else:
            cgpa_bins['9-10'] += 1

    days = 30
    window_start = timezone.now().date() - timedelta(days=days)
    offers_last_n = Student.objects.filter(offer_date__gte=window_start)
    offer_rate = round(offers_last_n.count() / total_students * 100, 2) if total_students > 0 else 0

    skill_freq = {}
    for s in Student.objects.exclude(skills='').values_list('skills', flat=True):
        for skill in [x.strip().lower() for x in s.split(',') if x.strip()]:
            skill_freq[skill] = skill_freq.get(skill, 0) + 1

    sorted_skills = sorted(skill_freq.items(), key=lambda kv: kv[1], reverse=True)
    top_skills = [{'skill': skill, 'count': cnt, 'pf': round(cnt / total_students * 100, 1)} for skill, cnt in sorted_skills[:5]]
    top_students = list(Student.objects.order_by('-cgpa')[:5])

    is_student = False
    student_id = None
    if request.user.is_authenticated:
        if request.user.groups.filter(name='student').exists():
            is_student = True
            student_profile = Student.objects.filter(user=request.user).first()
            if student_profile:
                student_id = student_profile.id

    three_days_ago = timezone.now() - timedelta(days=3)
    from .models import Job
    new_jobs = Job.objects.filter(created_at__gte=three_days_ago).order_by('-created_at')

    return render(request, 'home.html', {
        'total_students': total_students,
        'total_sessions': total_sessions,
        'total_questions': total_questions,
        'latest_session': latest_session,
        'branch_stats': branch_stats,
        'cgpa_bins': cgpa_bins,
        'offer_rate': offer_rate,
        'new_jobs': new_jobs,
        'offer_window': days,
        'top_skills': top_skills,
        'top_students': top_students,
        'is_student': is_student,
        'student_id': student_id,
    })


@login_required
def student_detail_dashboard(request, id):
    student = get_object_or_404(Student, id=id)

    if request.user.groups.filter(name='student').exists() and student.user and student.user != request.user:
        return HttpResponseForbidden('Students can only view their own dashboard.')

    sessions = student.mockinterviewsession_set.order_by('-updated_at')
    session_data = []
    for session in sessions:
        msgs = session.messages.all()
        rated_scores = [m.score for m in msgs if m.score is not None]
        session_data.append({
            'id': session.id,
            'updated_at': session.updated_at,
            'questions': session.question_count(),
            'avg_score': round(sum(rated_scores) / len(rated_scores), 2) if rated_scores else None,
        })

    from .ml_model import predict_placement
    # Estimate an average ATS score of 70 if unverified via actual analyzer to populate base dashboard metrics
    placement_prob = predict_placement(student.cgpa, student.skills, ats_score=70)

    return render(request, 'students/student_dashboard.html', {
        'student': student,
        'sessions': session_data,
        'placement_prob': placement_prob
    })


def metrics_json(request):
    total_students = Student.objects.count()
    total_sessions = MockInterviewSession.objects.count()
    total_questions = MockInterviewQuestion.objects.count()
    offer_rate = round(Student.objects.filter(offer_date__isnull=False).count() / total_students * 100, 2) if total_students else 0

    return JsonResponse({
        'total_students': total_students,
        'total_sessions': total_sessions,
        'total_questions': total_questions,
        'offer_rate': offer_rate,
    })


class MockInterviewQuestionListCreateAPI(generics.ListCreateAPIView):
    queryset = MockInterviewQuestion.objects.order_by('id')
    serializer_class = MockInterviewQuestionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class MockInterviewQuestionRetrieveUpdateDestroyAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = MockInterviewQuestion.objects.order_by('id')
    serializer_class = MockInterviewQuestionSerializer
    lookup_field = 'id'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class MockInterviewSessionListAPI(generics.ListAPIView):
    queryset = MockInterviewSession.objects.order_by('-updated_at')
    serializer_class = MockInterviewSessionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class MockInterviewSessionRetrieveAPI(generics.RetrieveAPIView):
    queryset = MockInterviewSession.objects.order_by('-updated_at')
    serializer_class = MockInterviewSessionSerializer
    lookup_field = 'id'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class StudentListCreateAPI(generics.ListCreateAPIView):
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Student.objects.order_by('name')
        q = self.request.GET.get('q', None)
        branch = self.request.GET.get('branch', None)
        min_cgpa = self.request.GET.get('min_cgpa', None)

        if q:
            queryset = queryset.filter(name__icontains=q)
        if branch:
            queryset = queryset.filter(branch=branch)
        if min_cgpa:
            try:
                queryset = queryset.filter(cgpa__gte=float(min_cgpa))
            except ValueError:
                pass

        return queryset


class StudentRetrieveUpdateDestroyAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = Student.objects.order_by('name')
    serializer_class = StudentSerializer
    lookup_field = 'id'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

from openai import OpenAI, RateLimitError
from django.conf import settings
from django.shortcuts import redirect

@login_required
def chatbot(request):
    if not request.session.get('chat_history'):
        request.session['chat_history'] = [
            {"role": "system", "content": "You are a friendly, encouraging interview coach. Provide concise, actionable advice."}
        ]
        
    if request.method == "POST" and request.POST.get("action") == "clear":
        request.session['chat_history'] = [
            {"role": "system", "content": "You are a friendly, encouraging interview coach. Provide concise, actionable advice."}
        ]
        request.session.modified = True
        return redirect('students:chatbot')
        
    if request.method == "POST":
        user_message = request.POST.get("message", "").strip()
        if user_message:
            chat_history = request.session.get('chat_history', [])
            chat_history.append({"role": "user", "content": user_message})
            
            try:
                client = OpenAI(api_key=getattr(settings, 'OPENAI_API_KEY', ''))
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=chat_history
                )
                ai_response = completion.choices[0].message.content
                chat_history.append({"role": "assistant", "content": ai_response})
            except RateLimitError:
                ai_response = "⚠️ OpenAI Rate Limit Exceeded: You have exhausted your API quota. Please check your billing details or use a valid active API key."
                chat_history.append({"role": "assistant", "content": ai_response})
            except Exception as e:
                ai_response = f"⚠️ Connect Error: I'm having trouble connecting to OpenAI. ({str(e)})"
                chat_history.append({"role": "assistant", "content": ai_response})
                
            request.session['chat_history'] = chat_history
            request.session.modified = True
            
        return redirect('students:chatbot')

    chat_history = request.session.get('chat_history', [])
    display_history = [m for m in chat_history if m['role'] != 'system']
    
    return render(request, "students/chatbot.html", {"chat_history": display_history})

@login_required
def resume_analyzer(request, student_id=None):
    import json
    import re
    
    analysis_result = None
    prefill_text = ""
    prefill_role = ""
    student = None
    
    all_students = Student.objects.all().order_by('name')
    
    if student_id:
        student = get_object_or_404(Student, id=student_id)
        prefill_role = f"{student.branch} {student.course} Role"
        if student.resume:
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(student.resume.path)
                for page in reader.pages:
                    prefill_text += page.extract_text() + "\n"
            except Exception as e:
                prefill_text = f"Error reading PDF: {str(e)}"
    
    prediction = None
    student_obj = student if student_id else None
    
    if request.method == "POST":
        post_student_id = request.POST.get("student_id")
        resume_text = request.POST.get("resume_text", "").strip()
        job_role = request.POST.get("job_role", "").strip()
        
        # If user picked a student from the dropdown instead of pasting text
        if post_student_id:
            student_obj = get_object_or_404(Student, id=post_student_id)
            job_role = f"{student_obj.branch} {student_obj.course} Role"
            resume_text = ""
            if student_obj.resume:
                try:
                    import PyPDF2
                    reader = PyPDF2.PdfReader(student_obj.resume.path)
                    for page in reader.pages:
                        resume_text += page.extract_text() + "\n"
                except Exception as e:
                    analysis_result = {"error": f"Error reading PDF: {str(e)}"}
            else:
                analysis_result = {"error": f"{student_obj.name} does not have a resume uploaded!"}
                
        prefill_text = resume_text
        prefill_role = job_role
        
        if resume_text:
            try:
                client = OpenAI(api_key=getattr(settings, 'OPENAI_API_KEY', ''))
                prompt = (
                    "You are an expert ATS System and Technical Recruiter. Analyze the following resume text. "
                    f"{'Evaluate it specifically for the role of ' + job_role + '. ' if job_role else ''}"
                    "Provide a JSON response strictly with these keys: "
                    "'score' (integer 0-100), 'strengths' (list of 3 strings), 'weaknesses' (list of 3 strings), and 'summary' (short paragraph)."
                    f"\n\nResume Text:\n{resume_text}"
                )
                
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}]
                )
                
                content = completion.choices[0].message.content
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    analysis_result = json.loads(json_str)
                else:
                    analysis_result = {"error": "Failed to parse API response. Please try again or use simpler resume formatting."}
            except RateLimitError:
                analysis_result = {"error": "OpenAI Rate Limit Exceeded. Quota limit reached on the API key."}
            except Exception as e:
                analysis_result = {"error": f"API Error: {str(e)}"}
                
            # Perform ML Placement Prediction if student is linked
            if student_obj and analysis_result and 'score' in analysis_result:
                from .ml_model import predict_placement
                prediction = predict_placement(student_obj.cgpa, student_obj.skills, analysis_result.get('score'))
                
    return render(request, "students/resume_analyzer.html", {"analysis": analysis_result, "prefill_text": prefill_text, "prefill_role": prefill_role, "prediction": prediction, "student": student_obj, "all_students": all_students})

from .forms import StudentRegistrationForm, OfficerRegistrationForm, RecruiterRegistrationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm

def student_register(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.profile.role = 'student'
            user.profile.branch = form.cleaned_data.get('branch')
            user.profile.skills = form.cleaned_data.get('skills')
            user.profile.save()
            
            # Keep previous Student model compatibility
            from .models import Student
            Student.objects.create(
                user=user, name=user.username, email=form.cleaned_data.get('email'), course='B.Tech', branch=user.profile.branch, skills=user.profile.skills
            )
            
            login(request, user)
            messages.success(request, 'Student registered successfully!')
            return redirect('students:student_dashboard')
    else:
        form = StudentRegistrationForm()
        
    for field in form.fields.values():
        field.widget.attrs.update({'class': 'form-control bg-light'})
    return render(request, 'registration/register_student.html', {'form': form})


def officer_register(request):
    if request.method == 'POST':
        form = OfficerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.profile.role = 'officer'
            user.profile.save()
            login(request, user)
            messages.success(request, 'Placement Officer registered successfully!')
            return redirect('students:officer_dashboard')
    else:
        form = OfficerRegistrationForm()
        
    for field in form.fields.values():
        field.widget.attrs.update({'class': 'form-control bg-light'})
    return render(request, 'registration/register_officer.html', {'form': form})


def recruiter_register(request):
    if request.method == 'POST':
        form = RecruiterRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.profile.role = 'recruiter'
            user.profile.save()
            login(request, user)
            messages.success(request, 'Recruiter registered successfully!')
            return redirect('students:recruiter_dashboard')
    else:
        form = RecruiterRegistrationForm()
        
    for field in form.fields.values():
        field.widget.attrs.update({'class': 'form-control bg-light'})
    return render(request, 'registration/register_recruiter.html', {'form': form})


def register(request):
    return render(request, 'registration/register.html')

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                
                if user.is_superuser or (hasattr(user, 'profile') and user.profile.role == 'admin'):
                    return redirect('students:admin_dashboard')
                elif hasattr(user, 'profile') and user.profile.role == 'officer':
                    return redirect('students:officer_dashboard')
                else:
                    return redirect('students:student_dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
        
    for field in form.fields.values():
        field.widget.attrs.update({'class': 'form-control bg-light'})
    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('home')


from django.contrib.auth.models import User
from .models import Job, Application, Interview, Student

@login_required
@role_required('student')
def student_dashboard(request):
    student = Student.objects.filter(user=request.user).first()
    if not student:
        return HttpResponseForbidden('Student profile missing.')
        
    total_jobs = Job.objects.count()
    jobs_applied = student.applications.count()
    
    interviews = student.interviews.all()
    int_scores = [i.score for i in interviews if i.score is not None]
    avg_score = round(sum(int_scores)/len(int_scores), 1) if int_scores else 0
    
    from django.utils import timezone
    from datetime import timedelta
    
    three_days_ago = timezone.now() - timedelta(days=3)
    latest_jobs = Job.objects.filter(created_at__gte=three_days_ago).order_by('-created_at')
    new_jobs_count = latest_jobs.count()
    
    fields_to_check = ['name', 'phone', 'course', 'branch', 'skills', 'bio', 'projects', 'certifications', 'linkedin_url', 'github_url', 'profile_picture', 'resume']
    filled = sum(1 for field in fields_to_check if getattr(student, field))
    completion_percentage = int((filled / len(fields_to_check)) * 100)
    
    context = {
        'total_jobs': total_jobs,
        'jobs_applied': jobs_applied,
        'avg_score': avg_score,
        'placement_status': student.placement_status,
        'latest_jobs': latest_jobs[:5],
        'new_jobs_count': new_jobs_count,
        'completion_percentage': completion_percentage,
        'recent_jobs': Job.objects.order_by('-created_at')[:5]
    }
    return render(request, 'dashboards/student_dashboard.html', context)

@login_required
@role_required('officer')
def officer_dashboard(request):
    total_students = Student.objects.count()
    eligible_students = Student.objects.filter(cgpa__gte=7.0).count()
    total_jobs = Job.objects.count()
    selected_candidates = Application.objects.filter(status='Selected').count()
    total_applications = Application.objects.count()
    top_students = Student.objects.order_by('-cgpa')[:5]
    
    context = {
        'total_students': total_students,
        'eligible_students': eligible_students,
        'total_jobs': total_jobs,
        'selected_candidates': selected_candidates,
        'total_applications': total_applications,
        'top_students': top_students
    }
    return render(request, 'dashboards/officer_dashboard.html', context)


@login_required
@role_required('recruiter')
def recruiter_dashboard(request):
    from .models import Job, Application
    # Filter jobs posted by this user if we want specific ownership, 
    # but for now let's show all or just a general view if ownership is not yet in Job model.
    # To be safe, let's assume they want to see all jobs they can manage.
    total_jobs = Job.objects.count()
    total_applications = Application.objects.count()
    latest_jobs = Job.objects.order_by('-created_at')[:5]
    
    context = {
        'total_jobs': total_jobs,
        'total_applications': total_applications,
        'latest_jobs': latest_jobs,
    }
    return render(request, 'dashboards/recruiter_dashboard.html', context)

@login_required
@role_required('admin')
def admin_dashboard(request):
    total_users = User.objects.count()
    total_placements = Application.objects.filter(status='Selected').count()
    total_students = Student.objects.count()
    
    success_rate = 0
    if total_students > 0:
        success_rate = round((total_placements / total_students) * 100, 1)
        
    context = {
        'total_users': total_users,
        'total_placements': total_placements,
        'success_rate': success_rate
    }
    return render(request, 'dashboards/admin_dashboard.html', context)

# ================================
# JOB PANEL VIEWS
# ================================
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.http import HttpResponseRedirect
from .models import Job, Application

def calculate_match_score(student_skills, job_skills):
    if not student_skills or not job_skills:
        return 0
    s_skills = set([s.strip().lower() for s in student_skills.split(',') if s.strip()])
    j_skills = set([s.strip().lower() for s in job_skills.split(',') if s.strip()])
    if not j_skills:
        return 0
    match_count = len(s_skills.intersection(j_skills))
    return int((match_count / len(j_skills)) * 100)

@login_required
def job_list(request):
    from django.utils import timezone
    from datetime import timedelta
    
    jobs = Job.objects.all().order_by('-created_at')
    
    three_days_ago = timezone.now() - timedelta(days=3)
    new_jobs = Job.objects.filter(created_at__gte=three_days_ago).order_by('-created_at')
    
    search = request.GET.get('q')
    if search:
        jobs = jobs.filter(Q(title__icontains=search) | Q(company__icontains=search))
        
    req_cgpa = request.GET.get('cgpa')
    if req_cgpa:
        try:
            jobs = jobs.filter(required_cgpa__lte=float(req_cgpa))
        except ValueError:
            pass
            
    skill = request.GET.get('skill')
    if skill:
        jobs = jobs.filter(required_skills__icontains=skill)
        
    recommended_jobs = []
    if hasattr(request.user, 'student') and getattr(request.user.profile, 'role', '') == 'student':
        student_skills = request.user.student.skills
        applied_job_ids = request.user.student.applications.values_list('job_id', flat=True)
        available_jobs = Job.objects.exclude(id__in=applied_job_ids)
        
        job_scores = []
        for job in available_jobs:
            score = calculate_match_score(student_skills, job.required_skills)
            if score > 0:
                job.match_score = score
                job_scores.append(job)
        
        job_scores.sort(key=lambda x: x.match_score, reverse=True)
        recommended_jobs = job_scores[:3]

    return render(request, 'jobs/job_list.html', {
        'jobs': jobs,
        'new_jobs': new_jobs,
        'recommended_jobs': recommended_jobs
    })

@login_required
def job_detail(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    student = None
    has_applied = False
    is_eligible = True
    
    has_profile = hasattr(request.user, 'profile')
    user_role = request.user.profile.role if has_profile else ''

    if user_role == 'student' and hasattr(request.user, 'student'):
        student = request.user.student
        has_applied = Application.objects.filter(student=student, job=job).exists()
        if float(student.cgpa) < float(job.required_cgpa):
            is_eligible = False
            
    applications = job.applications.all() if getattr(request.user, 'is_superuser', False) or user_role in ['admin', 'officer'] else None

    return render(request, 'jobs/job_detail.html', {
        'job': job,
        'has_applied': has_applied,
        'is_eligible': is_eligible,
        'student': student,
        'applications': applications
    })

@login_required
def apply_job(request, job_id):
    if not hasattr(request.user, 'student'):
        messages.error(request, "Only students can apply.")
        return HttpResponseRedirect(reverse('students:job_detail', args=[job_id]))
        
    job = get_object_or_404(Job, id=job_id)
    student = request.user.student
    
    if float(student.cgpa) < float(job.required_cgpa):
        messages.error(request, "Not eligible for this job.")
        return HttpResponseRedirect(reverse('students:job_detail', args=[job_id]))
        
    if Application.objects.filter(student=student, job=job).exists():
        messages.warning(request, "You have already applied.")
    else:
        Application.objects.create(student=student, job=job)
        messages.success(request, "Application submitted successfully!")
        
    return HttpResponseRedirect(reverse('students:job_detail', args=[job_id]))

@login_required
def my_applications(request):
    if not hasattr(request.user, 'student'):
        return HttpResponseRedirect('/')
    applications = request.user.student.applications.all().order_by('-applied_on')
    return render(request, 'jobs/my_applications.html', {'applications': applications})

@login_required
def add_job(request):
    is_staff = getattr(request.user, 'is_superuser', False) or (hasattr(request.user, 'profile') and request.user.profile.role in ['officer', 'admin', 'recruiter'])
    if not is_staff:
        return HttpResponseRedirect('/')
    if request.method == 'POST':
        new_job = Job.objects.create(
            title=request.POST.get('title'),
            company=request.POST.get('company'),
            description=request.POST.get('description'),
            location=request.POST.get('location'),
            salary=request.POST.get('salary'),
            required_cgpa=request.POST.get('required_cgpa') or 0.00,
            required_skills=request.POST.get('required_skills', ''),
            deadline=request.POST.get('deadline')
        )
        
        # Dispatch Notification Alerts and Emails 
        try:
            from django.core.mail import send_mail
            from .models import Student, Notification
            from django.urls import reverse
            
            eligible_students = Student.objects.filter(cgpa__gte=new_job.required_cgpa)
            
            # Build absolute URL for email link
            job_url = request.build_absolute_uri(reverse('students:job_detail', args=[new_job.id]))
            
            # 1. Create In-App Notifications
            notifications = []
            for student in eligible_students:
                if student.user:
                    notifications.append(Notification(
                        user=student.user,
                        message=f"New Job Posted: {new_job.title} at {new_job.company}",
                        link=reverse('students:job_detail', args=[new_job.id])
                    ))
            if notifications:
                Notification.objects.bulk_create(notifications)
                
            # 2. Send Emails
            recipient_list = [student.email for student in eligible_students if student.email]
            if recipient_list:
                subject = "New Job Posted!"
                message = f"A new job has been added that matches your profile.\n\n" \
                          f"Job Title: {new_job.title}\n" \
                          f"Company: {new_job.company}\n" \
                          f"Required CGPA: {new_job.required_cgpa}\n" \
                          f"Apply link: {job_url}\n\n" \
                          f"Best,\nPlacement Cell"
                
                send_mail(
                    subject,
                    message,
                    'placements@spc.example.com',
                    recipient_list,
                    fail_silently=True,
                )
        except Exception as e:
            # Prevent failure from breaking the job creation process
            print(f"Failed to send email alerts or create notifications: {e}")
            pass

        messages.success(request, "Job created successfully and alerts Dispatched!")
        return HttpResponseRedirect(reverse('students:job_list'))
    return render(request, 'jobs/add_job.html')

@login_required
def edit_job(request, job_id):
    is_staff = getattr(request.user, 'is_superuser', False) or (hasattr(request.user, 'profile') and request.user.profile.role in ['officer', 'admin'])
    if not is_staff:
        return HttpResponseRedirect('/')
    job = get_object_or_404(Job, id=job_id)
    if request.method == 'POST':
        job.title = request.POST.get('title')
        job.company = request.POST.get('company')
        job.description = request.POST.get('description')
        job.location = request.POST.get('location')
        job.salary = request.POST.get('salary')
        job.required_cgpa = request.POST.get('required_cgpa') or 0.00
        job.required_skills = request.POST.get('required_skills', '')
        job.deadline = request.POST.get('deadline')
        job.save()
        messages.success(request, "Job updated successfully.")
        return HttpResponseRedirect(reverse('students:job_detail', args=[job.id]))
    return render(request, 'jobs/add_job.html', {'job': job})

@login_required
def delete_job(request, job_id):
    is_staff = getattr(request.user, 'is_superuser', False) or (hasattr(request.user, 'profile') and request.user.profile.role in ['officer', 'admin', 'recruiter'])
    if not is_staff:
        return HttpResponseRedirect('/')
    job = get_object_or_404(Job, id=job_id)
    if request.method == 'POST':
        job.delete()
        messages.success(request, "Job deleted successfully.")
        return HttpResponseRedirect(reverse('students:job_list'))
    return render(request, 'jobs/delete_job.html', {'job': job})


@login_required
@role_required('officer', 'recruiter', 'admin')
def recruiter_job_candidates(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    students = Student.objects.all().order_by('-cgpa')
    
    # Simple AI/Match Scoring
    matched_students = []
    for student in students:
        score = calculate_match_score(student.skills, job.required_skills)
        if score > 0:
            student.ai_score = score
            matched_students.append(student)
    
    matched_students.sort(key=lambda x: x.ai_score, reverse=True)
    
    return render(request, 'jobs/job_candidates.html', {
        'job': job,
        'candidates': matched_students[:10],  # Top 10 matched
    })

from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import JobSerializer, ApplicationSerializer

class JobListCreateAPI(generics.ListCreateAPIView):
    queryset = Job.objects.order_by('-created_at')
    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class JobRetrieveUpdateDestroyAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = Job.objects.order_by('-created_at')
    serializer_class = JobSerializer
    lookup_field = 'id'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class ApplicationListCreateAPI(generics.ListCreateAPIView):
    queryset = Application.objects.order_by('-applied_on')
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class ApplicationRetrieveUpdateDestroyAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = Application.objects.order_by('-applied_on')
    serializer_class = ApplicationSerializer
    lookup_field = 'id'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class AnalyticsAPI(APIView):
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        total_users = User.objects.count()
        total_placements = Application.objects.filter(status='Selected').count()
        total_students = Student.objects.count()
        success_rate = round((total_placements / total_students) * 100, 1) if total_students > 0 else 0
        
        return Response({
            'total_users': total_users,
            'total_students': total_students,
            'total_placements': total_placements,
            'success_rate': success_rate
        })

from django.db.models import Q
from .forms import StudentProfileForm

@login_required
def student_profile_view(request, id=None):
    is_student = hasattr(request.user, 'profile') and request.user.profile.role == 'student'
    is_staff = hasattr(request.user, 'profile') and request.user.profile.role in ['officer', 'admin'] or request.user.is_superuser
    
    if id:
        if not is_staff and not getattr(request.user, 'student', None) == Student.objects.filter(id=id).first():
            messages.error(request, "Permission denied.")
            return HttpResponseRedirect('/')
        student = get_object_or_404(Student, id=id)
    else:
        if not is_student:
            return HttpResponseRedirect('/')
        student = getattr(request.user, 'student', None)
        if not student:
            messages.warning(request, "Profile not initially deployed. Please configure your footprint.")
            return HttpResponseRedirect(reverse('students:student_profile_update'))
    
    # Calculate Completion % dynamically
    fields_to_check = ['name', 'phone', 'course', 'branch', 'skills', 'bio', 'projects', 'certifications', 'linkedin_url', 'github_url', 'profile_picture', 'resume']
    filled = sum(1 for field in fields_to_check if getattr(student, field))
    completion_percentage = int((filled / len(fields_to_check)) * 100)

    return render(request, 'profiles/profile.html', {'student': student, 'completion_percentage': completion_percentage})

@login_required
def student_profile_update(request):
    is_student = hasattr(request.user, 'profile') and request.user.profile.role == 'student'
    if not is_student:
        return HttpResponseRedirect('/')
    
    student = getattr(request.user, 'student', None)
    
    if request.method == 'POST':
        form = StudentProfileForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            new_student = form.save(commit=False)
            new_student.user = request.user
            if not new_student.email:
                new_student.email = request.user.email
            new_student.save()
            messages.success(request, "Profile successfully rebuilt!")
            return HttpResponseRedirect(reverse('students:student_profile_view'))
    else:
        form = StudentProfileForm(instance=student)
        
    return render(request, 'profiles/edit_profile.html', {'form': form})

@login_required
def all_students_list(request):
    is_staff = getattr(request.user, 'is_superuser', False) or (hasattr(request.user, 'profile') and request.user.profile.role in ['officer', 'admin'])
    if not is_staff:
        messages.error(request, "Access Denied: Officer clearance required.")
        return HttpResponseRedirect('/')
        
    query = request.GET.get('q', '')
    branch = request.GET.get('branch', '')
    cgpa = request.GET.get('cgpa', '')
    
    students = Student.objects.all().order_by('-cgpa', '-created_at')
    
    if query:
        students = students.filter(
            Q(name__icontains=query) | 
            Q(skills__icontains=query)
        )
    if branch:
        students = students.filter(branch__iexact=branch)
    if cgpa:
        try:
            students = students.filter(cgpa__gte=float(cgpa))
        except ValueError:
            pass
            
    return render(request, 'profiles/student_list.html', {
        'students': students, 
        'query': query,
        'selected_branch': branch,
        'min_cgpa': cgpa
    })
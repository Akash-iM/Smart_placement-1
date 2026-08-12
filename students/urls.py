
from django.urls import path
from . import views

app_name = "students"

urlpatterns = [
    path('', views.student_list, name='student_list'),
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('add/', views.add_student, name='add_student'),
    path('edit/<int:id>/', views.edit_student, name='edit_student'),
    path('delete/<int:id>/', views.delete_student, name='delete_student'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('mock_interview/', views.mock_interview, name='mock_interview'),
    path('mock-interview/api/', views.mock_interview_api, name='mock_interview_api'),

    path('dashboard/<int:id>/', views.student_detail_dashboard, name='student_detail_dashboard'),
    path('mock-interview/', views.mock_interview, name='mock_interview'),
    path('metrics/', views.metrics_json, name='metrics_json'),
    path('mock_interviewpractice/', views.mock_interview, name='mock_interviewpractice'),
    path('resume-analyzer/', views.resume_analyzer, name='resume_analyzer'),
    path('resume-analyzer/<int:student_id>/', views.resume_analyzer, name='resume_analyzer_student'),
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    
    # Profile & Directory URLs
    path('profile/', views.student_profile_view, name='student_profile_view'),
    path('profile/<int:id>/', views.student_profile_view, name='student_profile_view_param'),
    path('profile/edit/', views.student_profile_update, name='student_profile_update'),
    path('all/', views.all_students_list, name='all_students_list'),
    
    # Job Panel URLs
    path('jobs/', views.job_list, name='job_list'),
    path('jobs/<int:job_id>/', views.job_detail, name='job_detail'),
    path('jobs/add/', views.add_job, name='add_job'),
    path('jobs/edit/<int:job_id>/', views.edit_job, name='edit_job'),
    path('jobs/delete/<int:job_id>/', views.delete_job, name='delete_job'),
    path('jobs/apply/<int:job_id>/', views.apply_job, name='apply_job'),
    path('my-applications/', views.my_applications, name='my_applications'),
    
    # Recruiter URLs
    path('recruiter/dashboard/', views.recruiter_dashboard, name='recruiter_dashboard'),
    path('jobs/<int:job_id>/candidates/', views.recruiter_job_candidates, name='recruiter_job_candidates'),
]
from django.urls import path
from .views import (
    StudentListCreateAPI,
    StudentRetrieveUpdateDestroyAPI,
    MockInterviewQuestionListCreateAPI,
    MockInterviewQuestionRetrieveUpdateDestroyAPI,
    MockInterviewSessionListAPI,
    MockInterviewSessionRetrieveAPI,
    JobListCreateAPI,
    JobRetrieveUpdateDestroyAPI,
    ApplicationListCreateAPI,
    ApplicationRetrieveUpdateDestroyAPI,
    AnalyticsAPI,
)

urlpatterns = [
    path('', StudentListCreateAPI.as_view(), name='api_student_list_create'),
    path('<int:id>/', StudentRetrieveUpdateDestroyAPI.as_view(), name='api_student_detail'),

    path('questions/', MockInterviewQuestionListCreateAPI.as_view(), name='api_mock_question_list_create'),
    path('questions/<int:id>/', MockInterviewQuestionRetrieveUpdateDestroyAPI.as_view(), name='api_mock_question_detail'),

    path('sessions/', MockInterviewSessionListAPI.as_view(), name='api_mock_session_list'),
    path('sessions/<int:id>/', MockInterviewSessionRetrieveAPI.as_view(), name='api_mock_session_detail'),
    
    path('jobs/', JobListCreateAPI.as_view(), name='api_job_list_create'),
    path('jobs/<int:id>/', JobRetrieveUpdateDestroyAPI.as_view(), name='api_job_detail'),
    
    path('applications/', ApplicationListCreateAPI.as_view(), name='api_application_list_create'),
    path('applications/<int:id>/', ApplicationRetrieveUpdateDestroyAPI.as_view(), name='api_application_detail'),
    
    path('analytics/', AnalyticsAPI.as_view(), name='api_analytics'),
]
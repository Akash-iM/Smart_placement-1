from django.contrib import admin
from django.urls import path, include
from students.views import home

from students.views import api_docs
import students.views as students_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('students/', include('students.urls')),
    path('api/students/', include('students.api_urls')),
    path('api-docs/', api_docs, name='api_docs'),
    
    path('login/', students_views.login_view, name='login'),
    path('logout/', students_views.logout_view, name='logout'),
    path('register/', students_views.register, name='register'),
    path('register/student/', students_views.student_register, name='student_register'),
    path('register/officer/', students_views.officer_register, name='officer_register'),
    path('register/recruiter/', students_views.recruiter_register, name='recruiter_register'),
    
    path('recruiter/dashboard/', students_views.recruiter_dashboard, name='recruiter_dashboard'),
    path('officer/dashboard/', students_views.officer_dashboard, name='officer_dashboard'),
    path('student/dashboard/', students_views.student_dashboard, name='student_dashboard'),
    path('admin-dashboard/', students_views.admin_dashboard, name='admin_dashboard'),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

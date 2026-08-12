from django.contrib import admin
from .models import Student, MockInterviewQuestion, MockInterviewSession, MockInterviewMessage

admin.site.register(Student)
admin.site.register(MockInterviewQuestion)
admin.site.register(MockInterviewSession)
admin.site.register(MockInterviewMessage)





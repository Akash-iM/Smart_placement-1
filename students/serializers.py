from rest_framework import serializers
from .models import Student, MockInterviewQuestion, MockInterviewSession, MockInterviewMessage, Job, Application

class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = '__all__'

class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = '__all__'

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['id', 'name', 'email', 'course', 'branch', 'cgpa', 'skills', 'resume', 'placement_status', 'created_at', 'updated_at']


class MockInterviewQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MockInterviewQuestion
        fields = ['id', 'text', 'category', 'created_at']


class MockInterviewMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MockInterviewMessage
        fields = ['id', 'sender', 'text', 'score', 'created_at']


class MockInterviewSessionSerializer(serializers.ModelSerializer):
    messages = MockInterviewMessageSerializer(many=True, read_only=True)

    class Meta:
        model = MockInterviewSession
        fields = ['id', 'student', 'created_at', 'updated_at', 'messages']

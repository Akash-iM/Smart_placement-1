from openai import OpenAI
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

class Profile(models.Model):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('officer', 'Placement Officer'),
        ('recruiter', 'Recruiter'),
        ('admin', 'Admin'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    cgpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    branch = models.CharField(max_length=100, blank=True)
    skills = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    @property
    def unread_notifications_count(self):
        return self.user.notifications.filter(is_read=False).count()

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()


class Student(models.Model):
    BRANCH_CHOICES = [
        ('CSE', 'Computer Science'),
        ('ECE', 'Electronics'),
        ('ME', 'Mechanical'),
        ('CE', 'Civil'),
        ('MGT', 'Management'),
    ]

    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL, help_text='Auth user linked to student')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True, help_text='Contact Number')
    course = models.CharField(max_length=100)
    branch = models.CharField(max_length=4, choices=BRANCH_CHOICES, default='CSE')
    cgpa = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    skills = models.CharField(max_length=255, blank=True, help_text='Comma-separated skills')
    projects = models.TextField(blank=True, null=True, help_text='Brief description of projects or comma separated')
    certifications = models.TextField(blank=True, null=True, help_text='List of certifications')
    linkedin_url = models.URLField(max_length=255, blank=True, null=True)
    github_url = models.URLField(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True, null=True, help_text='Short professional bio')
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True, help_text='Profile Picture Image')
    offer_date = models.DateField(null=True, blank=True, help_text='Date when candidate received an offer')
    resume = models.FileField(upload_to='resumes/', null=True, blank=True, help_text='Student Resume PDF')
    
    PLACEMENT_CHOICES = (
        ('Placed', 'Placed'),
        ('Not Placed', 'Not Placed')
    )
    placement_status = models.CharField(max_length=20, choices=PLACEMENT_CHOICES, default='Not Placed')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def has_offer(self):
        return self.offer_date is not None

    @property
    def offer_status(self):
        return 'Offered' if self.has_offer else 'Pending'

    @property
    def session_count(self):
        return self.mockinterviewsession_set.count()

    @property
    def avg_score(self):
        scores = self.mockinterviewsession_set.filter(messages__score__isnull=False).values_list('messages__score', flat=True)
        scores = [s for s in scores if s is not None]
        if not scores:
            return 0
        return round(sum(scores) / len(scores), 2)

    def __str__(self):
        return f"{self.name} ({self.email})"


class MockInterviewQuestion(models.Model):
    text = models.CharField(max_length=512)
    category = models.CharField(max_length=64, blank=True, default='General')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text


class MockInterviewSession(models.Model):
    student = models.ForeignKey(Student, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def question_count(self):
        return self.messages.count()

    def __str__(self):
        name = self.student.name if self.student else 'Anonymous'
        return f"{name} session {self.id}"


class MockInterviewMessage(models.Model):
    SESSION_SENDER_CHOICES = [
        ('user', 'User'),
        ('bot', 'Bot'),
    ]

    session = models.ForeignKey(MockInterviewSession, related_name='messages', on_delete=models.CASCADE)
    sender = models.CharField(max_length=4, choices=SESSION_SENDER_CHOICES)
    text = models.TextField()
    score = models.IntegerField(null=True, blank=True, help_text='Optional self-score 0-10')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender}: {self.text[:40]}"


def broadcast_dashboard_metrics():
    total_students = Student.objects.count()
    total_sessions = MockInterviewSession.objects.count()
    total_questions = MockInterviewQuestion.objects.count()
    offer_rate = round(Student.objects.filter(offer_date__isnull=False).count() / total_students * 100, 2) if total_students else 0

    payload = {
        'total_students': total_students,
        'total_sessions': total_sessions,
        'total_questions': total_questions,
        'offer_rate': offer_rate,
    }

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'dashboard_metrics',
        {
            'type': 'metrics_update',
            'payload': payload,
        }
    )


@receiver(post_save, sender=Student)
@receiver(post_delete, sender=Student)
def student_metrics_update(sender, **kwargs):
    broadcast_dashboard_metrics()


@receiver(post_save, sender=MockInterviewSession)
@receiver(post_delete, sender=MockInterviewSession)
def session_metrics_update(sender, **kwargs):
    broadcast_dashboard_metrics()
    
class Job(models.Model):
    title = models.CharField(max_length=150)
    company = models.CharField(max_length=150)
    description = models.TextField()
    required_cgpa = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    required_skills = models.TextField(help_text="Comma separated skills")
    location = models.CharField(max_length=200, blank=True)
    salary = models.CharField(max_length=100, blank=True)
    deadline = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} at {self.company}"

class Application(models.Model):
    STATUS_CHOICES = (
        ('Applied', 'Applied'),
        ('Selected', 'Selected'),
        ('Rejected', 'Rejected')
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='applications')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Applied')
    score = models.IntegerField(null=True, blank=True, help_text="AI match score")
    applied_on = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('student', 'job')

    def __str__(self):
        return f"{self.student.name} - {self.job.title}"

class Interview(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='interviews')
    question = models.TextField()
    answer = models.TextField(blank=True)
    feedback = models.TextField(blank=True)
    score = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Interview for {self.student.name}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.message[:30]}"
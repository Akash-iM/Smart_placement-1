from django import forms
from .models import Student

class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['name', 'email', 'course', 'branch', 'cgpa', 'skills', 'offer_date', 'resume']

    def __init__(self, *args, **kwargs):
        super(StudentForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control bg-light px-3 py-2'
            if field_name == 'resume':
                field.widget.attrs['class'] = 'form-control bg-light'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Student.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('A student with this email already exists.')
        return email

    def clean_cgpa(self):
        cgpa = self.cleaned_data.get('cgpa')
        return cgpa
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile

class StudentRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control bg-light'}))
    branch = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control bg-light'}))
    skills = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-light', 'placeholder': 'Comma-separated skills'}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)

class OfficerRegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields

class RecruiterRegistrationForm(UserCreationForm):
    company_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control bg-light'}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)

class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['name', 'phone', 'course', 'branch', 'skills', 'bio', 'projects', 'certifications', 'linkedin_url', 'github_url', 'profile_picture', 'resume']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
            'projects': forms.Textarea(attrs={'rows': 3}),
            'certifications': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super(StudentProfileForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['profile_picture', 'resume']:
                field.widget.attrs.update({'class': 'form-control bg-light'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
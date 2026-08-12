import json
from django.urls import reverse
from django.test import TestCase
from django.contrib.auth.models import User
from .models import Student

class StudentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass', email='john@example.com')
        from django.contrib.auth.models import Group
        coordinator_group, _ = Group.objects.get_or_create(name='coordinator')
        self.user.groups.add(coordinator_group)
        self.user.save()
        self.client.force_login(self.user)
        self.student = Student.objects.create(name='John', email='john@example.com', course='CSE', branch='CSE', cgpa='8.50', skills='Python,Django', user=self.user)

    def test_add_student(self):
        resp = self.client.post(reverse('students:add_student'), {
            'name': 'A',
            'email': 'a@x.com',
            'course': 'C',
            'branch': 'ME',
            'cgpa': '7.25',
            'skills': 'Mechanics,AutoCAD'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Student.objects.count(), 2)

    def test_student_list_view(self):
        resp = self.client.get(reverse('students:student_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'John')

    def test_edit_student(self):
        url = reverse('students:edit_student', kwargs={'id': self.student.id})
        resp = self.client.post(url, {
            'name': 'John Updated',
            'email': 'john@example.com',
            'course': 'CSE',
            'branch': 'ECE',
            'cgpa': '9.00',
            'skills': 'Django,React'
        })
        self.assertEqual(resp.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.name, 'John Updated')
        self.assertEqual(str(self.student.cgpa), '9.00')
        self.assertEqual(self.student.branch, 'ECE')

    def test_delete_student(self):
        url = reverse('students:delete_student', kwargs={'id': self.student.id})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Student.objects.filter(id=self.student.id).exists())

    def test_api_list_and_create(self):
        list_resp = self.client.get('/api/students/')
        self.assertEqual(list_resp.status_code, 200)
        self.assertIn('john@example.com', [item['email'] for item in list_resp.json().get('results', [])])

        create_resp = self.client.post('/api/students/', {
            'name': 'API Student',
            'email': 'api@example.com',
            'course': 'AI',
            'branch': 'CSE',
            'cgpa': '8.9',
            'skills': 'python,ml'
            }, content_type='application/json')
        self.assertEqual(create_resp.status_code, 201)
        self.assertEqual(Student.objects.filter(email='api@example.com').count(), 1)

    def test_api_detail_update_delete(self):
        url = f'/api/students/{self.student.id}/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['name'], 'John')

        update_resp = self.client.put(url, {
            'name': 'JohnAPI',
            'email': 'john@example.com',
            'course': 'CSE',
            'branch': 'CSE',
            'cgpa': '9.5',
            'skills': 'Django'
            }, content_type='application/json')
        self.assertEqual(update_resp.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.name, 'JohnAPI')

        delete_resp = self.client.delete(url)
        self.assertEqual(delete_resp.status_code, 204)
        self.assertFalse(Student.objects.filter(id=self.student.id).exists())

    def test_api_filtering(self):
        Student.objects.create(name='Alice', email='alice@example.com', course='CS', branch='ECE', cgpa='9.20', skills='robotics')
        resp_q = self.client.get('/api/students/?q=Ali')
        self.assertEqual(resp_q.status_code, 200)
        self.assertEqual(len(resp_q.json()['results']), 1)

        resp_branch = self.client.get('/api/students/?branch=ECE')
        self.assertEqual(resp_branch.status_code, 200)
        self.assertTrue(len(resp_branch.json()['results']) >= 1)

        resp_cgpa = self.client.get('/api/students/?min_cgpa=9')
        self.assertEqual(resp_cgpa.status_code, 200)
        self.assertTrue(all(float(item['cgpa']) >= 9.0 for item in resp_cgpa.json()['results']))

    def test_mock_interview_api(self):
        body = {'question': 'Tell me about yourself'}
        resp = self.client.post('/students/mock-interview/api/', json.dumps(body), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('answer', resp.json())

        body = {'question': ''}
        resp = self.client.post('/students/mock-interview/api/', json.dumps(body), content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.json())

        resp = self.client.get('/students/mock-interview/api/')
        self.assertEqual(resp.status_code, 405)

    def test_mock_interview_session_history(self):
        body = {'question': 'What is your greatest strength?'}
        resp = self.client.post('/students/mock-interview/api/', json.dumps(body), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        session_id = data.get('session_id')
        self.assertIsNotNone(session_id)

        second = self.client.post('/students/mock-interview/api/', json.dumps({'question': 'Tell me about yourself', 'session_id': session_id}), content_type='application/json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json().get('session_id'), session_id)

    def test_unique_email_validation(self):
        resp = self.client.post(reverse('students:add_student'), {'name': 'Jane', 'email': 'john@example.com', 'course': 'ME'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'A student with this email already exists.')
        self.assertEqual(Student.objects.count(), 1)

    def test_invalid_email_format(self):
        resp = self.client.post(reverse('students:add_student'), {'name': 'Bob', 'email': 'invalid-email', 'course': 'ME'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Enter a valid email address.')
        self.assertEqual(Student.objects.count(), 1)

    def test_required_fields(self):
        resp = self.client.post(reverse('students:add_student'), {'name': '', 'email': '', 'course': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'This field is required.', count=5)
        self.assertEqual(Student.objects.count(), 1)

    def test_home_page_shows_metrics(self):
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Dashboard')
        self.assertContains(resp, str(Student.objects.count()))

    def test_student_dashboard_detail(self):
        resp = self.client.get(reverse('students:student_detail_dashboard', kwargs={'id': self.student.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Mock Interview Sessions')
        self.assertContains(resp, 'Offer status')

    def test_metrics_json(self):
        resp = self.client.get(reverse('students:metrics_json'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total_students'], 1)
        self.assertIn('offer_rate', data)

    def test_api_docs_page(self):
        resp = self.client.get(reverse('api_docs'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '/api/students/')

    def test_home_charts_present(self):
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="branchChart"')
        self.assertContains(resp, 'id="cgpaChart"')

    def test_password_reset_flow(self):
        from django.core import mail

        resp = self.client.get(reverse('password_reset'))
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(reverse('password_reset'), {'email': 'john@example.com'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Password reset', mail.outbox[0].subject)

    def test_api_question_endpoints(self):
        # create question
        q_resp = self.client.post('/api/students/questions/', {'text': 'What is Django?', 'category': 'framework'}, content_type='application/json')
        self.assertEqual(q_resp.status_code, 201)
        q_id = q_resp.json().get('id')
        self.assertIsNotNone(q_id)

        get_resp = self.client.get(f'/api/students/questions/{q_id}/')
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()['text'], 'What is Django?')

        update_resp = self.client.put(f'/api/students/questions/{q_id}/', {'text': 'Explain Django', 'category': 'framework'}, content_type='application/json')
        self.assertEqual(update_resp.status_code, 200)

        del_resp = self.client.delete(f'/api/students/questions/{q_id}/')
        self.assertEqual(del_resp.status_code, 204)

    def test_api_session_list(self):
        resp = self.client.get('/api/students/sessions/')
        self.assertEqual(resp.status_code, 200)



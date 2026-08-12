from django.db import migrations


def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for group_name in ['coordinator', 'recruiter', 'student']:
        Group.objects.get_or_create(name=group_name)


class Migration(migrations.Migration):
    dependencies = [
        ('students', '0007_student_offer_date'),
    ]

    operations = [
        migrations.RunPython(create_groups),
    ]

# Generated by Django 4.2 on 2023-05-31 19:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointment', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='exercise',
            name='video_link',
            field=models.URLField(null=True),
        ),
    ]

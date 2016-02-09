# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-01-14 15:10
from __future__ import unicode_literals

import datetime
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0024_auto_20160114_1502'),
    ]

    operations = [
        migrations.CreateModel(
            name='Virus_Batch',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('virus_type', models.CharField(blank=True, max_length=255, null=True)),
                ('description', models.CharField(blank=True, max_length=255, null=True)),
                ('virus_source', models.CharField(blank=True, max_length=255, null=True)),
                ('date_time_made', models.DateTimeField(blank=True, default=datetime.datetime.now, null=True)),
                ('nominal_titer', models.FloatField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Virus_Injection',
            fields=[
                ('action_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='subjects.Action')),
                ('injection_volume', models.FloatField(blank=True, null=True)),
                ('rate_of_injection', models.FloatField(blank=True, null=True)),
                ('injection_type', models.CharField(blank=True, choices=[('I', 'Iontophoresis'), ('P', 'Pressure')], default='I', max_length=1, null=True)),
                ('virus_batch_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='subjects.Virus_Batch')),
            ],
            bases=('subjects.action',),
        ),
    ]

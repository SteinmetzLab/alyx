# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-06-21 12:30
from __future__ import unicode_literals

import datetime
import django.contrib.postgres.fields
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('actual_severity', models.IntegerField(blank=True, choices=[(0, 'Mild'), (1, 'Moderate'), (2, 'Severe'), (3, 'Non-recovery')], default=1, null=True)),
                ('narrative', models.TextField(blank=True, null=True)),
                ('start_date_time', models.DateTimeField(blank=True, default=datetime.datetime.now, null=True)),
                ('end_date_time', models.DateTimeField(blank=True, null=True)),
                ('tags', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=255), blank=True, help_text='Short text strings to allow searching', null=True, size=30)),
                ('json', django.contrib.postgres.fields.jsonb.JSONField(blank=True, help_text='Structured data, formatted in a user-defined way', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Procedure',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Short procedure name', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Detailed description of the procedure', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Protocol',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='The protocol name', max_length=255)),
                ('number', models.IntegerField(blank=True, help_text='The protocol number', null=True)),
                ('severity_limit', models.IntegerField(blank=True, choices=[(0, 'Mild'), (1, 'Moderate'), (2, 'Severe'), (3, 'Non-recovery')], default=1, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Experiment',
            fields=[
                ('action_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='actions.Action')),
            ],
            bases=('actions.action',),
        ),
        migrations.CreateModel(
            name='Note',
            fields=[
                ('action_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='actions.Action')),
            ],
            bases=('actions.action',),
        ),
        migrations.CreateModel(
            name='Surgery',
            fields=[
                ('action_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='actions.Action')),
            ],
            options={
                'verbose_name_plural': 'surgeries',
            },
            bases=('actions.action',),
        ),
        migrations.CreateModel(
            name='VirusInjection',
            fields=[
                ('action_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='actions.Action')),
                ('injection_volume', models.FloatField(blank=True, help_text='Volume in nanoliters', null=True)),
                ('rate_of_injection', models.FloatField(blank=True, help_text='TODO: Nanoliters per second / per minute?', null=True)),
                ('injection_type', models.CharField(blank=True, choices=[('I', 'Iontophoresis'), ('P', 'Pressure')], default='I', help_text='Whether the injection was through iontophoresis or pressure', max_length=1, null=True)),
            ],
            bases=('actions.action',),
        ),
        migrations.CreateModel(
            name='WaterAdministration',
            fields=[
                ('action_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='actions.Action')),
                ('water_administered', models.FloatField(help_text='Water administered, in millilitres')),
            ],
            bases=('actions.action',),
        ),
        migrations.CreateModel(
            name='Weighing',
            fields=[
                ('action_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='actions.Action')),
                ('weight', models.FloatField(help_text='Weight in grams')),
            ],
            bases=('actions.action',),
        ),
        migrations.AddField(
            model_name='procedure',
            name='protocol',
            field=models.ForeignKey(blank=True, help_text='The associated protocol', null=True, on_delete=django.db.models.deletion.CASCADE, to='actions.Protocol'),
        ),
    ]
# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-01-10 17:13
from __future__ import unicode_literals

from django.db import migrations
import djorm_pgarray.fields


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0009_weighing'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='tags',
            field=djorm_pgarray.fields.ArrayField(blank=True, default=None, null=True),
        ),
    ]

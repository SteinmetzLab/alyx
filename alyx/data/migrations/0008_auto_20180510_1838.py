# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-05-10 18:38
from __future__ import unicode_literals
import os
import random
import string

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


def random_string():
    s = '-unnamed-' + ''.join(random.choice(string.ascii_lowercase) for _ in range(16))
    return s


def update_data_instances(apps, schema_editor):
    DataFormat = apps.get_model("data", "DataFormat")
    # Update the DataFormat file extension (only keep the extension).
    db_alias = schema_editor.connection.alias
    for df in DataFormat.objects.using(db_alias).all():
        if not df.filename_pattern:
            df.delete()
        assert df.name
        df.filename_pattern = os.path.splitext(df.filename_pattern)[-1]
        df.full_clean()
        df.save()

    DataFormat.objects.using(db_alias).create(name='unknown', filename_pattern='.-',
                                              id='54338e66-9613-4270-9c5d-9da347cb52cc')

    DatasetType = apps.get_model("data", "DatasetType")
    for dst in DatasetType.objects.using(db_alias).all():
        # Remove the parent links so that deleting the parents do not delete the children too
        # (because of CASCADE deleting).
        dst.parent_dataset_type = None
        dst.save()
        if not dst.filename_pattern or '.*.*' in dst.filename_pattern:
            dst.delete()

    DatasetType.objects.using(db_alias).create(name='unknown', filename_pattern='-',
                                               id='e8bef994-3aa3-4f46-8bf5-18fa3ae87ef2')

    Dataset = apps.get_model("data", "Dataset")
    for d in Dataset.objects.using(db_alias).filter(name__isnull=True):
        d.name = random_string()
        d.full_clean()
        d.save()

    FileRecord = apps.get_model("data", "FileRecord")
    for fr in FileRecord.objects.using(db_alias).filter(relative_path__isnull=True):
        fr.relative_path = random_string()
        fr.full_clean()
        fr.save()


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0007_auto_20180416_0910'),
    ]

    operations = [
        migrations.RunPython(update_data_instances),
    ]

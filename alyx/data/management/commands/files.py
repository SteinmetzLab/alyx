import logging
from django.core.management import BaseCommand
from django.db.models import Count, Q

from actions.models import Session
from data import transfers
from data.models import Dataset, DatasetType, DataRepository, FileRecord
from subjects.models import Project

logging.getLogger(__name__).setLevel(logging.WARNING)


def _iter_datasets(dataset_id=None, limit=None, user=None):
    dataset_ids = [dataset_id] if dataset_id is not None else transfers._incomplete_dataset_ids()
    datasets = Dataset.objects.filter(pk__in=dataset_ids).order_by('-created_datetime')
    if user is not None:
        datasets = datasets.filter(created_by__username=user)
    if limit is not None:
        datasets = datasets[:int(limit)]
    for dataset in datasets:
        yield dataset


def _create_missing_file_records_main_globus(dry_run=False, project=None):
    projects = Project.objects.all()
    if project:
        projects = projects.filter(name=project)
    for p in projects:
        repos = p.repositories.filter(globus_is_personal=False)
        dsets = Dataset.objects.filter(session__project=p)
        for r in repos:
            dsr = dsets.annotate(rep_count=Count('file_records',
                                                 filter=Q(file_records__data_repository=r)))
            dsr = dsr.order_by('session__start_time')
            to_create = dsr.filter(rep_count=0)
            for ds in to_create:
                if ds.file_records.count():
                    rel_path = ds.file_records.first().relative_path
                else:
                    continue  # we do not want to create filerecords if none exist for a dataset
                print('create', r.name, rel_path)
                if not dry_run:
                    FileRecord.objects.create(dataset=ds,
                                              relative_path=rel_path,
                                              data_repository=r)


def _create_missing_file_records(dry_run=False):
    # Create missing file records for sessions that have been manually assigned
    # to a project.
    for s in Session.objects.select_related('project').prefetch_related(
            'data_dataset_session_related',
            'data_dataset_session_related__file_records',
    ).filter(project__isnull=False):  # noqa
        # All repositories associated to the session's projects.
        expected_repos = set(s.project.repositories.all())
        # Going through the datasets.
        for d in s.data_dataset_session_related.all():
            fr = d.file_records.first()
            # Find the repositories which do not have a FileRecord yet.
            actual_repos = set([fr.data_repository for fr in d.file_records.all()])
            repos_to_create = expected_repos - actual_repos
            # Create them.
            for dr in repos_to_create:
                print('Create', fr.relative_path, ' in', dr.name)
                if not dry_run:
                    fr = FileRecord.objects.create(dataset=fr.dataset,
                                                   relative_path=fr.relative_path,
                                                   data_repository=dr)
                    print("Created %s" % fr)


class Command(BaseCommand):
    help = "Manage files"

    def add_arguments(self, parser):
        parser.add_argument('action', help='Action')
        parser.add_argument('dataset', nargs='?', help='Dataset')
        parser.add_argument('--project', help='Only sync for project')
        parser.add_argument('--dry', action='store_true', help='dry run')
        parser.add_argument('--data-repository', help='data repository')
        parser.add_argument('--path', help='path')
        parser.add_argument('--limit', help='limit to a maximum number of datasets')
        parser.add_argument('--user', help='select datasets created by a given user')

    def handle(self, *args, **options):
        action = options.get('action')
        dataset_id = options.get('dataset')
        path = options.get('path')
        data_repository = options.get('data_repository')
        limit = options.get('limit')
        user = options.get('user')
        dry = options.get('dry')
        project = options.get('project')

        if action == 'bulksync':
            _create_missing_file_records_main_globus(dry_run=dry, project=project)
            transfers.bulk_sync(dry_run=dry, project=project)

        if action == 'bulktransfer':
            transfers.bulk_transfer(dry_run=dry, project=project)

        if action == 'login':
            transfers.create_globus_token()
            self.stdout.write(self.style.SUCCESS("Login successful."))

        if action == 'sync':
            _create_missing_file_records(dry_run=dry)
            for dataset in _iter_datasets(dataset_id, limit=limit, user=user):
                self.stdout.write("Synchronizing file status of %s" % str(dataset))
                if not dry:
                    transfers.update_file_exists(dataset)

        if action == 'syncfast':
            with open(path, 'r') as f:
                existing = {p.strip(): True for p in f.readlines()}
            for fr in FileRecord.objects.filter(exists=False):
                path = transfers._get_absolute_path(fr)
                if existing.get(path, None):
                    self.stdout.write("File %s exists, updating." % path)
                    fr.exists = True
                    fr.save()

        if action == 'transfer':
            for dataset in _iter_datasets(dataset_id, limit=limit, user=user):
                to_transfer = transfers.transfers_required(dataset)
                for transfer in to_transfer:
                    self.stdout.write(
                        "Launch Globus transfer from %s:%s to %s:%s." % (
                            transfer['source_data_repository'],
                            transfer['source_path'],
                            transfer['destination_data_repository'],
                            transfer['destination_path'],
                        )
                    )
                    if not dry:
                        transfers.start_globus_transfer(
                            transfer['source_file_record'], transfer['destination_file_record'])

        if action == 'migrate':
            dr = DataRepository.objects.get(name='flatiron_cortexlab')
            dr.data_url = 'http://ibl.flatironinstitute.org/cortexlab/Subjects/'
            dr.save()

            qs = DatasetType.objects.filter(filename_pattern__isnull=False)
            dt = None
            for d in FileRecord.objects.all().select_related('dataset'):
                try:
                    dt = transfers.get_dataset_type(d.relative_path, qs=qs)
                except ValueError:
                    dt = None
                    continue
                if d.dataset.dataset_type_id != dt.pk:
                    print("Different dataset type for %s : old %s new %s" % (
                        d.relative_path, d.dataset.dataset_type.name, dt.name))
                    d.dataset.dataset_type_id = dt.pk
                    d.dataset.save()
                dt = None

        if action == 'normalize_relative_paths':
            for fr in FileRecord.objects.all():
                p = fr.relative_path or ''
                if '\\' in p:
                    fr.relative_path = p.replace('\\', '/')
                    try:
                        fr.full_clean()
                    except Exception as e:
                        print(fr)
                        print(e)
                        continue
                    fr.save()
                if '//' in p:
                    fr.relative_path = p.replace('//', '/')
                    try:
                        fr.full_clean()
                    except Exception as e:
                        print(fr)
                        print(e)
                        continue
                    fr.save()

        if action == 'autoregister':
            if not data_repository:
                raise ValueError("Please specify a data_repository.")
            data_repository = DataRepository.objects.get(name=data_repository)
            for dir_path, filenames in transfers.iter_registered_directories(
                    data_repository=data_repository, path=path):
                print(dir_path, filenames)

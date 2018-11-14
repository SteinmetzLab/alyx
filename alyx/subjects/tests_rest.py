from django.contrib.auth import get_user_model
from django.urls import reverse
from alyx.base import BaseTests
from actions.models import WaterAdministration, Weighing


class APISubjectsTests(BaseTests):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')

    def test_list_subjects(self):
        url = reverse('subject-list')
        response = self.client.get(url)
        self.ar(response)
        d = response.data
        self.assertTrue(len(d) > 200)
        self.assertTrue(set(('nickname', 'id', 'responsible_user', 'death_date',
                             'line', 'litter', 'sex', 'genotype', 'url')) <= set(d[0]))

    def test_list_alive_subjects(self):
        url = reverse('subject-list') + '?alive=True&stock=True'
        response = self.client.get(url)
        self.ar(response)
        d = response.data
        self.assertTrue(len(d) > 200)
        self.assertTrue(set(('nickname', 'id', 'responsible_user', 'death_date')) <= set(d[0]))

        # also test that you can get some back when asking for non-stock
        url = reverse('subject-list') + '?alive=True&stock=False'
        response = self.client.get(url)
        self.ar(response)
        d = response.data
        self.assertTrue(len(d) > 0)
        self.assertTrue(set(('nickname', 'id', 'responsible_user', 'death_date')) <= set(d[0]))

    def test_subject_1(self):
        # test the individual subject endpoint, i.e. when you ask for a subject by name
        url = reverse('subject-list')
        response = self.client.get(url)
        self.ar(response)
        d = response.data

        # Ask for the first subject
        response = self.client.get(d[0]['url'])
        self.ar(response)
        d = response.data

        self.assertTrue(set(('nickname', 'id', 'responsible_user', 'death_date', 'line', 'litter',
                             'sex', 'genotype', 'url', 'expected_water',
                             'remaining_water', 'weighings', 'projects',
                             'water_administrations')) <= set(d))

    def test_list_projects(self):
        url = reverse('project-list')
        self.client.post(url, {'name': 'test_project'})
        response = self.client.get(url)
        self.ar(response)
        d = response.data
        self.assertEqual(d[0]['name'], 'test_project')

    def test_subject_water_administration(self):
        subject = WaterAdministration.objects.first().subject
        url = reverse('subject-detail', kwargs={'nickname': subject.nickname})
        response = self.client.get(url)
        self.ar(response)
        d = response.data

        self.assertTrue('water_administrations' in d)
        self.assertTrue(d['water_administrations'])
        wa = set(d['water_administrations'][0])
        self.assertTrue(set(('date_time', 'water_administered', 'water_type', 'url')) <= wa)

    def test_subject_weighing(self):
        subject = Weighing.objects.first().subject
        url = reverse('subject-detail', kwargs={'nickname': subject.nickname})
        response = self.client.get(url)
        self.ar(response)
        d = response.data

        self.assertTrue('weighings' in d)
        self.assertTrue(d['weighings'])
        w = set(d['weighings'][0])
        self.assertTrue(set(('date_time', 'weight', 'url')) <= w)

    def test_subject_filter_water_restricted(self):
        # first makes sure the endpoint only returns alive subjects
        url = reverse('subject-list') + '?water_restricted=True'
        response = self.client.get(url)
        self.ar(response)
        swr = response.data
        self.assertTrue([d['alive'] for d in swr])
        url = reverse('subject-list') + '?water_restricted=False'
        non_swr = self.client.get(url).data
        self.assertTrue([d['alive'] for d in non_swr])
        # paranoid: query dead subjects, alive subjects and make sure all wr subjects are
        # within the alive set but excluded from the dead set
        url = reverse('subject-list') + '?alive=False'
        dead = self.client.get(url).data
        url = reverse('subject-list') + '?alive=True'
        alive = self.client.get(url).data
        id_alive = set([d['id'] for d in alive])
        id_dead = set([d['id'] for d in dead])
        id_swr = set([d['id'] for d in swr])
        id_nonswr = set([d['id'] for d in non_swr])
        self.assertEqual(id_swr.intersection(id_alive), id_swr)
        self.assertTrue(len(id_swr.intersection(id_dead)) == 0)
        self.assertEqual(id_nonswr.intersection(id_alive), id_nonswr)
        self.assertTrue(len(id_nonswr.intersection(id_dead)) == 0)

    def test_subject_restricted(self):
        url = reverse('water-restricted-subject-list')
        response = self.client.get(url)
        self.ar(response)
        d = response.data

        self.assertTrue(set(('nickname', 'expected_water',
                             'remaining_water')) <= set(d[0]))

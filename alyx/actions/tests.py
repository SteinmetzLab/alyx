import datetime
import numpy as np
from django.test import TestCase
from django.utils import timezone

from alyx import base
from misc.models import Lab
from actions.water_control import date
from actions.models import (
    WaterAdministration, WaterRestriction, WaterType, Weighing,
    Notification, check_weighing, check_water_administration)
from subjects.models import Subject


class WaterControlTests(TestCase):
    def setUp(self):
        # create some water types
        wtypes = ['Water', 'Hydrogel', 'CA 5% Hydrogel', 'CA 5%', 'Sucrose 10%']
        for wt in wtypes:
            WaterType.objects.create(name=wt)
        # create a subject
        lab = Lab.objects.create(name='lab')
        self.sub = Subject.objects.create(nickname='bigboy', birth_date='2018-09-01', lab=lab)
        # 50 days of loosing weight and getting 0.98 mL water
        self.start_date = datetime.datetime(year=2018, month=10, day=1)
        for n, w in enumerate(np.linspace(25, 20, 50)):
            date_w = datetime.timedelta(days=n) + self.start_date
            Weighing.objects.create(weight=w, subject=self.sub, date_time=date_w)
            WaterAdministration.objects.create(
                water_administered=0.98,
                subject=self.sub,
                date_time=date_w)
        # first test assert that water administrations previously created have the correct default
        wa = WaterAdministration.objects.filter(subject=self.sub)
        self.assertTrue(wa.values_list('water_type__name').distinct()[0][0] == 'Water')

    def test_00_create_first_water_restriction(self):
        # Create an initial Water Restriction
        start_wr = self.start_date + datetime.timedelta(days=5)
        water_type = WaterType.objects.get(name='CA 5% Hydrogel')
        WaterRestriction.objects.create(subject=self.sub, start_time=start_wr,
                                        water_type=water_type)
        # from now on new water administrations should have water_type as default
        wa = WaterAdministration.objects.create(
            water_administered=1.02,
            subject=self.sub,
            date_time=datetime.datetime.now())
        self.assertEqual(water_type, wa.water_type)

    def test_water_administration_expected(self):
        wc = self.sub.water_control
        wa = WaterAdministration.objects.filter(subject=self.sub)
        # the method from the wa model should return the expectation at the corresponding date
        self.assertTrue(wa[0].expected() == wc.expected_water(date=wa[0].date_time.date()))
        self.assertTrue(wa[40].expected() == wc.expected_water(date=wa[40].date_time.date()))


class NotificationTests(TestCase):
    def setUp(self):
        base.DISABLE_MAIL = True
        self.lab = Lab.objects.create(name='testlab', reference_weight_pct=.85)
        self.subject = Subject.objects.create(
            nickname='test', birth_date=date('2018-01-01'), lab=self.lab)
        Weighing.objects.create(
            subject=self.subject, weight=10,
            date_time=timezone.datetime(2018, 6, 1, 12, 0, 0)
        )
        self.water_restriction = WaterRestriction.objects.create(
            subject=self.subject,
            start_time=timezone.datetime(2018, 6, 2, 12, 0, 0),
            reference_weight=10.,
        )
        self.water_administration = WaterAdministration.objects.create(
            subject=self.subject,
            date_time=timezone.datetime(2018, 6, 3, 12, 0, 0),
            water_administered=10,
        )
        self.date = date('2018-06-10')

    def tearDown(self):
        base.DISABLE_MAIL = False

    def test_notif_0(self):
        Weighing.objects.create(
            subject=self.subject, weight=9,
            date_time=timezone.datetime(2018, 6, 9, 8, 0, 0)
        )
        check_weighing(self.subject, date=self.date)
        self.assertTrue(len(Notification.objects.all()) == 0)

    def test_notif_1(self):
        Weighing.objects.create(
            subject=self.subject, weight=7,
            date_time=timezone.datetime(2018, 6, 9, 12, 0, 0)
        )
        check_weighing(self.subject, date=self.date)
        notif = Notification.objects.last()
        self.assertTrue(notif.title.startswith('WARNING'))

    def test_notif_2(self):
        Weighing.objects.create(
            subject=self.subject, weight=8.6,
            date_time=timezone.datetime(2018, 6, 9, 16, 0, 0)
        )
        check_weighing(self.subject, date=self.date)
        notif = Notification.objects.last()
        self.assertTrue(notif.title.startswith('Warning'))

    def test_water_1(self):
        date = timezone.datetime(2018, 6, 3, 16, 0, 0)
        check_water_administration(self.subject, date=date)
        notif = Notification.objects.last()
        self.assertTrue(notif is None)

        date = timezone.datetime(2018, 6, 4, 12, 0, 0)
        check_water_administration(self.subject, date=date)
        notif = Notification.objects.last()
        self.assertTrue(notif is not None)

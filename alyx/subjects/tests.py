import logging
from operator import attrgetter
import os.path as op
import sys
from uuid import UUID
import warnings

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test.client import RequestFactory

from .admin import mysite

logger = logging.getLogger(__file__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


DATA_DIR = op.abspath(op.join(op.dirname(__file__), '../../data'))


class MyTestsMeta(type):
    """Metaclass to generate one test per model dynamically."""
    def __new__(cls, name, bases, attrs):
        classes = sorted(mysite._registry, key=attrgetter('__name__'))
        for my_class in classes:
            name = my_class.__name__
            attrs['test_%s' % name] = cls.gen(my_class)
        return super(MyTestsMeta, cls).__new__(cls, name, bases, attrs)

    @classmethod
    def gen(cls, my_class):
        # Return a testcase that tests ``x``.
        def fn(self):
            self._test_class(my_class)
        return fn


class ModelAdminTests(TestCase, metaclass=MyTestsMeta):
    def setUp(self):
        # Fail on warning.
        # warnings.simplefilter("error")

        from misc.models import Lab
        self.site = mysite
        self.factory = RequestFactory()
        request = self.factory.get('/')
        request.csrf_processing_done = True
        self.request = request
        self.users = [user for user in get_user_model().objects.filter(is_superuser=True)]
        self.lab = Lab.objects.first()
        assert self.lab is not None

    def tearDown(self):
        warnings.simplefilter('default')

    @classmethod
    def setUpTestData(cls):
        call_command('loaddata', op.join(DATA_DIR, 'all_dumped_anon.json.gz'), verbosity=1)

    def ar(self, r):
        r.render()
        self.assertEqual(r.status_code, 200)

    def _test_list_change(self, ma):
        # List of subjects.
        r = ma.changelist_view(self.request)
        logger.debug("User %s, testing list %s.",
                     self.request.user.username, ma.model.__name__)
        self.ar(r)

        # Test the add page.
        if ma.has_add_permission(self.request):
            r = ma.add_view(self.request)
            logger.debug("User %s, testing add %s.",
                         self.request.user.username, ma.model.__name__)
            self.ar(r)

        # Get the first subject.
        qs = ma.get_queryset(self.request)
        if not len(qs):
            return
        subj = qs[0]

        # Test the change page.
        identifier = subj.id.hex if isinstance(subj.id, UUID) else str(subj.id)
        r = ma.change_view(self.request, identifier)
        logger.debug("User %s, testing change %s %s.",
                     self.request.user.username, ma.model.__name__, identifier)
        self.ar(r)

        # TODO: test saving

    def _test_class(self, cls):
        for user in self.users:  # test with different users
            self.request.user = user
            self._test_list_change(self.site._registry[cls])

    def test_history(self):
        from subjects.models import Subject, _has_field_changed

        s = Subject.objects.first()

        # Change the nickname.
        old_nickname = s.nickname
        s.nickname = 'new_nickname'
        s.save()

        self.assertEqual(s.json['history']['nickname'][-1]['value'], old_nickname)

        self.assertTrue(_has_field_changed(s, 'nickname'))
        self.assertFalse(_has_field_changed(s, 'death_date'))

        self.assertTrue(s.responsible_user is not None)
        self.assertFalse(_has_field_changed(s, 'responsible_user'))
        s.responsible_user = get_user_model().objects.last()
        self.assertTrue(_has_field_changed(s, 'responsible_user'))

    def test_zygosities_1(self):
        from subjects import models as m
        sequence = m.Sequence.objects.create(name='sequence')
        allele = m.Allele.objects.create(nickname='allele')
        line = m.Line.objects.create(nickname='line', lab=self.lab)
        line.alleles.add(allele)
        subject = m.Subject.objects.create(nickname='subject', line=line, lab=self.lab)
        assert len(subject.genotype.all()) == 0

        # Create a rule and a genotype test ; the subject should be automatically genotyped.
        rule = m.ZygosityRule.objects.create(
            line=line, allele=allele, sequence0=sequence, sequence0_result=1, zygosity=2)
        m.GenotypeTest.objects.create(
            subject=subject, sequence=sequence, test_result=1)

        a = m.Zygosity.objects.filter(subject=subject).first()
        assert len(subject.genotype.all()) == 1
        assert a.allele == allele
        assert a.subject == subject
        assert a.zygosity == 2

        # Change the rule
        rule.zygosity = 3
        rule.save()
        a = m.Zygosity.objects.filter(subject=subject).first()
        assert a.zygosity == 3

    def test_zygosities_2(self):
        from subjects import models as m
        sequence = m.Sequence.objects.create(name='sequence')
        allele = m.Allele.objects.create(nickname='allele')
        line = m.Line.objects.create(nickname='line', lab=self.lab)
        line.alleles.add(allele)

        # Create the parents.
        father = m.Subject.objects.create(
            nickname='father', sex='M', line=line, lab=self.lab)
        mother = m.Subject.objects.create(
            nickname='mother', sex='F', line=line, lab=self.lab)

        # Create the parents genotypes.
        m.Zygosity.objects.create(subject=father, allele=allele, zygosity=2)
        m.Zygosity.objects.create(subject=mother, allele=allele, zygosity=2)

        # Create the breeding pair and litter.
        bp = m.BreedingPair.objects.create(line=line, father=father, mother1=mother)
        litter = m.Litter.objects.create(line=line, breeding_pair=bp)

        # Create the subject.
        subject = m.Subject.objects.create(
            nickname='subject', line=line, litter=litter, lab=self.lab)
        z = m.Zygosity.objects.filter(subject=subject).first()
        assert z.zygosity == 2  # from parents

        # Create a rule and a genotype test ; the subject should be automatically genotyped.
        zr = m.ZygosityRule.objects.create(
            line=line, allele=allele, sequence0=sequence, sequence0_result=1, zygosity=0)
        m.GenotypeTest.objects.create(
            subject=subject, sequence=sequence, test_result=1)

        a = m.Zygosity.objects.filter(subject=subject).first()
        assert len(subject.genotype.all()) == 1
        assert a.allele == allele
        assert a.subject == subject
        assert a.zygosity == 0

        # Delete the rule.
        zr.delete()
        a = m.Zygosity.objects.filter(subject=subject).first()
        assert len(subject.genotype.all()) == 1
        assert a.allele == allele
        assert a.subject == subject
        assert a.zygosity == 2

    def test_zygosities_3(self):
        from subjects import models as m
        sequence = m.Sequence.objects.create(name='sequence')
        allele = m.Allele.objects.create(nickname='allele')
        allele_bis = m.Allele.objects.create(nickname='allele_bis')
        line = m.Line.objects.create(nickname='line', lab=self.lab)
        line.alleles.add(allele)

        # Create the parents.
        father = m.Subject.objects.create(
            nickname='father', sex='M', line=line, lab=self.lab)
        mother = m.Subject.objects.create(
            nickname='mother', sex='F', line=line, lab=self.lab)

        # Create the parents genotypes.
        m.Zygosity.objects.create(subject=father, allele=allele_bis, zygosity=2)
        m.Zygosity.objects.create(subject=mother, allele=allele, zygosity=1)

        # Create the breeding pair and litter.
        bp = m.BreedingPair.objects.create(line=line, father=father, mother1=mother)
        litter = m.Litter.objects.create(line=line, breeding_pair=bp)

        # Create the subject.
        subject = m.Subject.objects.create(
            nickname='subject', line=line, litter=litter, lab=self.lab)
        z = m.Zygosity.objects.filter(subject=subject)  # noqa
        return
        # TODO
        # ? assert z.zygosity == 2  # from parents
        # Create a rule and a genotype test ; the subject should be automatically genotyped.
        zr = m.ZygosityRule.objects.create(
            line=line, allele=allele, sequence0=sequence, sequence0_result=1, zygosity=0)
        m.GenotypeTest.objects.create(
            subject=subject, sequence=sequence, test_result=1)

        a = m.Zygosity.objects.filter(subject=subject).first()
        assert len(subject.genotype.all()) == 1
        assert a.allele == allele
        assert a.subject == subject
        assert a.zygosity == 0

        # Delete the rule.
        zr.delete()
        a = m.Zygosity.objects.filter(subject=subject).first()
        assert len(subject.genotype.all()) == 1
        assert a.allele == allele
        assert a.subject == subject
        assert a.zygosity == 2

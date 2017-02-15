from django import forms
from django.urls import reverse
from django.utils.html import format_html
from django.contrib import admin
from dal import autocomplete
from dal.forward import Const
from .models import *
from .views import _autoname_number
from actions.models import Surgery, Experiment


class ResponsibleUserListFilter(admin.SimpleListFilter):
    title = 'responsible user'
    parameter_name = 'responsible_user'

    def lookups(self, request, model_admin):
        return (
            ('m', 'Me'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'm':
            return queryset.filter(responsible_user=request.user)


class SubjectAliveListFilter(admin.SimpleListFilter):
    title = 'alive'
    parameter_name = 'alive'

    def lookups(self, request, model_admin):
        return (
            ('y', 'Yes'),
            ('n', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'y':
            return queryset.filter(death_date=None)
        if self.value() == 'n':
            return queryset.exclude(death_date=None)


class ZygosityInline(admin.TabularInline):
    model = Zygosity
    extra = 2  # how many rows to show


class GenotypeTestInline(admin.TabularInline):
    model = GenotypeTest
    extra = 2  # how many rows to show


class SurgeryInline(admin.TabularInline):
    model = Surgery
    extra = 1


class ExperimentInline(admin.TabularInline):
    model = Experiment
    extra = 1


class SubjectAdmin(admin.ModelAdmin):
    fieldsets = (
        ('SUBJECT', {'fields': ('nickname', 'sex', 'birth_date', 'age_days', 'responsible_user',
                                'death_date', 'ear_mark', 'notes')}),
        ('PROFILE', {'fields': ('species', 'strain', 'source', 'line')}),
        ('LITTER', {'fields': ('cage', 'litter',)}),
        ('WEIGHINGS/WATER', {'fields': ('water_restriction_date',
                                        'reference_weighing',
                                        'current_weighing',
                                        'implant_weight',
                                        'water_requirement_total',
                                        'water_requirement_remaining',
                                        'weighing_plot',
                                        )}),
    )

    list_display = ['nickname', 'birth_date', 'responsible_user',
                    'cage', 'mother', 'father',
                    'sex', 'alive']
    search_fields = ['nickname',
                     'responsible_user__first_name',
                     'responsible_user__last_name',
                     'responsible_user__username']
    readonly_fields = ('age_days',
                       'water_restriction_date',
                       'reference_weighing',
                       'current_weighing',
                       'water_requirement_total',
                       'water_requirement_remaining',
                       'weighing_plot',
                       )
    list_filter = [SubjectAliveListFilter, ResponsibleUserListFilter]
    inlines = [ZygosityInline, GenotypeTestInline,
               SurgeryInline, ExperimentInline]

    def mother(self, obj):
        if not obj.litter:
            return
        return obj.litter.mother

    def father(self, obj):
        if not obj.litter:
            return
        return obj.litter.father

    def weighing_plot(self, obj):
        url = reverse('weighing-plot', kwargs={'subject_id': obj.id})
        return format_html('<img src="{url}" />', url=url)


class SpeciesAdmin(admin.ModelAdmin):

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['binomial']
        return self.readonly_fields

    list_display = ['binomial', 'display_name']
    readonly_fields = []


class SubjectLitterInline(admin.TabularInline):
    model = Subject
    extra = 1
    fields = ('sex', 'cage', 'ear_mark', 'notes')
    show_change_link = True
    # TODO: genotype


class SubjectCageInline(admin.TabularInline):
    model = Subject
    extra = 1
    # fields = ('sex', 'ear_mark', 'notes')
    # TODO: genotype


class LineAdmin(admin.ModelAdmin):
    inlines = [SubjectLitterInline]


class LitterAdmin(admin.ModelAdmin):
    list_display = ['descriptive_name', 'mother', 'father']
    fields = ['line', 'descriptive_name', 'birth_date', 'notes',
              'mother', 'father', 'cage']

    inlines = [SubjectLitterInline]

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        # Delete objects marked to delete.
        for obj in formset.deleted_objects:
            obj.delete()
        litter = formset.instance
        mother = litter.mother
        to_copy = 'cage,species,strain,line,source,responsible_user'.split(',')
        for instance in instances:
            subj = instance
            subj.birth_date = litter.birth_date
            # Copy some fields from the mother to the subject.
            for field in to_copy:
                setattr(subj, field, getattr(mother, field))
            prefix = getattr(subj.line, 'name', 'UNKNOWN') + '_'
            i = _autoname_number(Subject, 'nickname', prefix)
            subj.nickname = '%s%04d' % (prefix, i)
            subj.save()
        formset.save_m2m()


class LitterInline(admin.TabularInline):
    model = Litter
    extra = 1
    show_change_link = True


class CageAdminForm(forms.ModelForm):

    cage_label = forms.CharField(
        widget=autocomplete.Select2(url='cage-label-autocomplete',
                                    forward=['line'],
                                    ),
        required=True,
    )
    mother = forms.ModelChoiceField(
        queryset=Subject.objects.filter(sex='F'),
        widget=autocomplete.ModelSelect2(url='subject-autocomplete',
                                         forward=['line',
                                                  Const('F', 'sex')],
                                         ),
        required=False,
    )
    father = forms.ModelChoiceField(
        queryset=Subject.objects.filter(sex='M'),
        widget=autocomplete.ModelSelect2(url='subject-autocomplete',
                                         forward=['line',
                                                  Const('M', 'sex')],
                                         ),
        required=False,
    )

    def save(self, commit=True):
        # Add the mice to the cage.
        mother = self.cleaned_data.get('mother', None)
        father = self.cleaned_data.get('father', None)
        if mother:
            mother.cage = self.instance
            mother.save()
        if father:
            father.cage = self.instance
            father.save()
        return super(CageAdminForm, self).save(commit=commit)

    class Meta:
        fields = '__all__'
        model = Cage


class CageAdmin(admin.ModelAdmin):
    form = CageAdminForm

    fields = ('line', 'cage_label', 'mother', 'father', 'type', 'location')
    inlines = [SubjectCageInline, LitterInline]


admin.site.register(Subject, SubjectAdmin)
admin.site.register(Litter, LitterAdmin)
admin.site.register(Species, SpeciesAdmin)

admin.site.register(Line, LineAdmin)
admin.site.register(Allele)
admin.site.register(Sequence)
admin.site.register(Strain)
admin.site.register(Source)
admin.site.register(Cage, CageAdmin)

from rest_framework import serializers
from subjects.models import Subject
from misc.models import Lab
from django.contrib.auth import get_user_model


class UserSerializer(serializers.ModelSerializer):
    subjects_responsible = serializers.SlugRelatedField(
        many=True, queryset=Subject.objects.all(), slug_field='nickname')

    @staticmethod
    def setup_eager_loading(queryset):
        queryset = queryset.prefetch_related('subjects_responsible')
        return queryset

    class Meta:
        model = get_user_model()
        fields = ('id', 'username', 'email', 'subjects_responsible', 'lab')


class LabSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Lab
        fields = ('name', 'institution', 'address', 'timezone',
                  'reference_weight_pct', 'zscore_weight_pct')
        lookup_field = 'name'
        extra_kwargs = {'url': {'view_name': 'lab-detail', 'lookup_field': 'name'}}

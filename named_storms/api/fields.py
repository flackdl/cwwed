from named_storms.models import NamedStormCoveredDataSnapshot


class SnapshotDefault:
    """
    An "advanced field default" to populate the most recent covered data snapshot for a storm
    https://www.django-rest-framework.org/api-guide/validators/#advanced-field-defaults
    """
    snapshot = None

    def set_context(self, serializer_field):
        # find the most recent covered data snapshot for this storm
        named_storm_id = serializer_field.context['request'].data.get('named_storm')
        qs = NamedStormCoveredDataSnapshot.objects.filter(named_storm__id=named_storm_id, date_completed__isnull=False)
        qs = qs.order_by('-date_completed')
        self.snapshot = qs.first()

    def __call__(self):
        return self.snapshot

    def __repr__(self):
        return '%s()' % self.__class__.__name__

class CurrentNsemPsaDefault:
    # expects "nsem" to exist in serializer context
    def set_context(self, serializer_field):
        self.nsem = serializer_field.context['nsem']

    def __call__(self):
        return self.nsem

class UserReferenceViewSetMixin:
    """
    ViewSet Mixin which includes the "request" object in the serializer context
    """

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

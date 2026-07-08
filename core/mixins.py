from django.contrib.auth.mixins import LoginRequiredMixin


class OwnerFilterMixin(LoginRequiredMixin):
    """Restricts querysets to objects owned by the current user.

    Subclasses must set ``model`` or override ``get_queryset``.
    """
    def get_queryset(self):
        return self.model.objects.filter(owner=self.request.user).select_related('owner')

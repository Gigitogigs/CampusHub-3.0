"""
universities/views.py
=====================
DRF views for the universities app.

These views handle the university registry API — creating, listing, updating,
and archiving universities.  They are intentionally separate from the accounts
app even though accounts holds identity FKs that point to universities.

Access model
------------
  UniversityListView      — Platform admin only (IsPlatformAdmin).
  UniversityCreateView    — Platform admin only (IsPlatformAdmin).
  UniversityDetailView    — Public (AllowAny); shows active universities only;
                            returns public subset of fields (no settings).
  UniversityUpdateView    — University admin (own university) OR platform admin
                            (any university).  Uses UniversityUpdatePermission.
  UniversityArchiveView   — Platform admin only (IsPlatformAdmin); soft-archives
                            by setting status = 'archived'.

URL wiring (config/urls.py)
---------------------------
  /api/v1/universities/           → universities.urls (canonical)
  /api/accounts/universities/     → compatibility alias in accounts.urls
                                    (points to the same views)
"""

from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.permissions import IsPlatformAdmin
from .models import University
from .permissions import UniversityUpdatePermission
from .serializers import UniversityPublicSerializer, UniversitySerializer


class UniversityListView(generics.ListAPIView):
    """
    GET /api/v1/universities/

    Returns all universities ordered by name.
    Restricted to platform administrators — regular university users should
    only ever interact with their own university via the update/detail endpoints.
    """

    queryset = University.objects.all().order_by("name")
    serializer_class = UniversitySerializer
    permission_classes = [IsPlatformAdmin]


class UniversityCreateView(generics.CreateAPIView):
    """
    POST /api/v1/universities/create/

    Creates a new university (onboarding flow).
    Restricted to platform administrators.

    The slug is auto-generated from the name if not supplied (see
    University.generate_slug()).
    """

    queryset = University.objects.all()
    serializer_class = UniversitySerializer
    permission_classes = [IsPlatformAdmin]


class UniversityDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/universities/public/<slug>/

    Returns the public profile of an active university.  Open to anyone
    (AllowAny) so that prospective students can look up a university before
    registering.

    Only active universities are returned; onboarding/suspended/archived
    universities return 404 through the filtered queryset.

    Uses UniversityPublicSerializer so private settings are never exposed.
    """

    queryset = University.objects.filter(status=University.Status.ACTIVE)
    serializer_class = UniversityPublicSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"


class UniversityUpdateView(generics.UpdateAPIView):
    """
    PATCH /api/v1/universities/<pk>/

    Allows updating a university's editable fields (name, timezone, settings,
    etc.).  Two principals may update:

    1. Platform admin — may update any university; queryset returns all.
    2. University admin — may update only their own university; queryset is
       filtered to `university_id = user.university_id`.

    get_queryset() implements this scoping so that attempting to update a
    university the caller doesn't own returns 404 (not 403), hiding the
    existence of other universities from university admins.

    Permission enforcement is split:
    - has_permission → UniversityUpdatePermission checks the user is active.
    - has_object_permission → checks platform admin OR university admin with
      a valid grant for the specific object.
    """

    serializer_class = UniversitySerializer
    permission_classes = [UniversityUpdatePermission]

    def get_queryset(self):
        """
        Return the universities this user is allowed to update.

        Platform admins get all universities (unrestricted).
        University admins get only their own university.
        """
        user = self.request.user
        using = (
            "ops"
            if getattr(self.request, "tenant_mode", None) == "platform"
            else None
        )
        if user.is_platform_admin(using=using):
            return University.objects.all()
        return University.objects.filter(id=user.university_id)


class UniversityArchiveView(generics.GenericAPIView):
    """
    POST /api/v1/universities/<pk>/archive/

    Soft-archives a university by setting its status to 'archived'.
    Idempotent: calling it on an already-archived university is a no-op.

    Restricted to platform administrators (IsPlatformAdmin).

    Returns the updated university representation with HTTP 200 on success.
    Archiving is irreversible through the API; re-activation requires a
    direct database change or a future admin command.
    """

    queryset = University.objects.all()
    serializer_class = UniversitySerializer
    permission_classes = [IsPlatformAdmin]

    def post(self, request, *args, **kwargs):
        """Archive the target university (idempotent)."""
        university = self.get_object()
        if university.status != University.Status.ARCHIVED:
            university.status = University.Status.ARCHIVED
            university.save(update_fields=["status", "updated_at"])
        return Response(
            self.get_serializer(university).data,
            status=status.HTTP_200_OK,
        )

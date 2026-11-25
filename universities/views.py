from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.permissions import IsPlatformAdminOrStaff
from .models import University
from .permissions import UniversityUpdatePermission
from .serializers import UniversityPublicSerializer, UniversitySerializer


class UniversityListView(generics.ListAPIView):
    queryset = University.objects.all().order_by("name")
    serializer_class = UniversitySerializer
    permission_classes = [IsPlatformAdminOrStaff]


class UniversityCreateView(generics.CreateAPIView):
    queryset = University.objects.all()
    serializer_class = UniversitySerializer
    permission_classes = [IsPlatformAdminOrStaff]


class UniversityDetailView(generics.RetrieveAPIView):
    queryset = University.objects.filter(status=University.Status.ACTIVE)
    serializer_class = UniversityPublicSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"


class UniversityUpdateView(generics.UpdateAPIView):
    serializer_class = UniversitySerializer
    permission_classes = [UniversityUpdatePermission]

    def get_queryset(self):
        user = self.request.user
        if user.platform_staff or user.is_staff or user.is_superuser:
            return University.objects.all()
        return University.objects.filter(id=user.university_id)


class UniversityArchiveView(generics.GenericAPIView):
    queryset = University.objects.all()
    serializer_class = UniversitySerializer
    permission_classes = [IsPlatformAdminOrStaff]

    def post(self, request, *args, **kwargs):
        university = self.get_object()
        if university.status != University.Status.ARCHIVED:
            university.status = University.Status.ARCHIVED
            university.save(update_fields=["status", "updated_at"])
        return Response(
            self.get_serializer(university).data,
            status=status.HTTP_200_OK,
        )

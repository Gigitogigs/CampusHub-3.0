from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import University, User
from ..core.permissions import IsPlatformAdmin, IsPlatformAdminOrStaff, IsStudent, IsUniversityAdmin
from .serializers import UniversitySerializer, UserSerializer, PublicUniversitySerializer


class UniversityListView(generics.ListAPIView):
    queryset = University.objects.all().order_by("name")
    serializer_class = UniversitySerializer
    permission_classes = [IsPlatformAdminOrStaff]


class UniversityCreateView(generics.CreateAPIView):
    queryset = University.objects.all()
    serializer_class = UniversitySerializer
    permission_classes = [IsPlatformAdminOrStaff]

class UniversityDetailView(generics.RetrieveAPIView):
    """View university's public details"""
    queryset = University.objects.filter(status=University.Status.ACTIVE)
    serializer_class = PublicUniversitySerializer
    permission_classes = [AllowAny]
    
class UniversityUpdateView(generics.UpdateAPIView):
    serializer_class = UniversitySerializer
    permission_classes = [IsPlatformAdminOrStaff, IsUniversityAdmin]

    def get_queryset(self):
        user = self.request.user

        if user.is_platform_admin:
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

class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, request, view):
        

class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsStudent, IsPlatformAdminOrStaff]

class UserUpdateView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsStudent]



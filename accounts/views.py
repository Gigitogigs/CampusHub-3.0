from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import University, User
from core.permissions import IsPlatformAdminOrStaff, IsStudent, IsUniversityAdmin, UniversityUpdatePermission
from .serializers import UniversitySerializer, UserSerializer, UniversityPublicSerializer, UserPublicSerializer
from .selectors import users_visible_to


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
    serializer_class = UniversityPublicSerializer
    permission_classes = [AllowAny]


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


class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return users_visible_to(self.request.user).order_by("full_name")


class UserDetailView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return users_visible_to(self.request.user)


class UserPublicDetailView(generics.RetrieveAPIView):
    """View authenticated user's public details"""
    queryset = User.objects.filter(deleted_at__isnull=True)
    serializer_class = UserPublicSerializer
    permission_classes = [IsAuthenticated]


class UserUpdateView(generics.UpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    # Gets user's own record or platform staff can update any user
    def get_queryset(self):
        return User.objects.filter(
            id=self.request.user.id,
            deleted_at__isnull=True,
        )



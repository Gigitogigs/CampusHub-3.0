from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import User
from .serializers import UserPublicSerializer, UserSerializer
from .selectors import users_visible_to


class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return users_visible_to(self.request.user).order_by("full_name")


class UserDetailView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

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



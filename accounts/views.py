"""
accounts/views.py
=================
DRF views for the accounts app.

All views in this module are intentionally *user-scoped*: they only expose data
about the requesting user (or users visible within the same tenant).  University
management lives in `universities/views.py`.

View inventory
--------------
UserListView
    Lists all users visible to the requesting user.  Uses `users_visible_to()`
    from selectors.py to enforce tenant scoping and platform-admin routing.
    Returns UserPublicSerializer (no sensitive fields).

UserDetailView
    Retrieves a single user by PK, scoped to `users_visible_to()` so the
    requesting user cannot fetch records outside their tenant.

UserPublicDetailView
    Retrieves the requesting user's own minimal public profile.  Useful for
    "who am I?" calls from the frontend.

UserUpdateView
    Allows a user to update their own record (email and full_name).  The
    queryset is restricted to the requesting user's own PK so it is impossible
    to update another user's record through this endpoint.

Routing note
------------
These views are mounted via accounts/urls.py at `/api/accounts/users/...`.
They are currently intentionally unmounted in production until the full
registration and role-grant service layer is in place.
"""

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import login, logout, authenticate

from .models import User, EmailToken
from .serializers import EmailVerificationSerializer, UserPublicSerializer, UserSerializer, UserCreateSerializer, LoginSerializer
from .selectors import users_visible_to

from .services import UnkownEmailDomain


class UserListView(generics.ListAPIView):
    """
    GET /api/accounts/users/

    Returns a paginated list of users visible to the requesting user.

    Scoping behaviour (enforced by users_visible_to()):
    - Platform admin: all non-deleted users, via the ops DB alias.
    - University user: all non-deleted users in the same university.
    - Anyone else: empty list (fail-closed).
    """

    serializer_class = UserPublicSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return users_visible_to(self.request.user).order_by("full_name")


class UserDetailView(generics.RetrieveAPIView):
    """
    GET /api/accounts/users/<pk>/

    Retrieves a single user by UUID, scoped to what the requesting user can
    see.  Attempting to fetch a user outside the allowed scope returns 404
    (not 403) so the existence of other users is not leaked.
    """

    serializer_class = UserPublicSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return users_visible_to(self.request.user).filter(
            pk=self.request.user.pk,
        )


class UserPublicDetailView(generics.RetrieveAPIView):
    """
    GET /api/accounts/users/me/

    Returns the requesting user's own public profile (id, full_name,
    university_name).  Equivalent to a "who am I?" endpoint.

    The queryset is filtered to the requesting user's own PK so the lookup_field
    can resolve correctly even though the URL does not carry a pk segment.
    """

    serializer_class = UserPublicSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return users_visible_to(self.request.user).filter(
            pk=self.request.user.pk,
        )


class UserUpdateView(generics.UpdateAPIView):
    """
    PATCH /api/accounts/users/me/update/

    Allows the requesting user to update their own profile fields.
    UserSerializer.read_only_fields ensures that status, platform_staff,
    auth_version, and other system-managed columns cannot be changed through
    this endpoint.

    The queryset is restricted to the requesting user's own PK — no other user
    can be targeted even if the client supplies a different pk in the URL.
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return users_visible_to(self.request.user).filter(pk=self.request.user.pk)


class SignupView(generics.CreateAPIView):
    serializer_class = UserCreateSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, _raw_token = register_user(**serializer.validated_data)
        except UnkownEmailDomain as exc:
            return Response({"email": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)

        #Trigger verification email here using _raw_token
        return Response(UserPublicSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = authenticate(
            request,
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
        )
        if user is None:
            return Response(
                {"detail": "Invalid credentials or account is not active"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class LogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)

class EmailVerificationView(generics.GenericAPIView):
    serializer_class = EmailVerificationSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

    
from django.urls import path
from . import views
from universities import views as uni_views

urlpatterns = [
    # User endpoints
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/me/', views.UserPublicDetailView.as_view(), name='user_me'),
    path('users/me/update/', views.UserUpdateView.as_view(), name='user_update'),
    path('users/<uuid:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    # Legacy university list endpoint (compatibility alias)
    path('universities/', uni_views.UniversityListView.as_view(), name='university_list_legacy'),
]

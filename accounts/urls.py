#Maps URL paths to views in the accounts app
from django.urls import path
from . import views
from universities import views as university_views

urlpatterns = [
    path(
        "universities/",
        university_views.UniversityListView.as_view(),
        name="university_list",
    ),
    path(
        "universities/create/",
        university_views.UniversityCreateView.as_view(),
        name="university_create",
    ),
    path(
        "universities/<uuid:pk>/archive/",
        university_views.UniversityArchiveView.as_view(),
        name="university_archive",
    ),
    path(
        "universities/<uuid:pk>/",
        university_views.UniversityUpdateView.as_view(),
        name="university_update",
    ),
]
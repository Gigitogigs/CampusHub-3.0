#Maps URL paths to views in the accounts app
from django.urls import path
from . import views

urlpatterns = [
    path(
        "universities/",
        views.UniversityListView.as_view(),
        name="university_list",
    ),
    path(
        "universities/create/",
        views.UniversityCreateView.as_view(),
        name="university_create",
    ),
    path(
        "universities/<uuid:pk>/archive/",
        views.UniversityArchiveView.as_view(),
        name="university_archive",
    ),
    path(
        "universities/<uuid:pk>/",
        views.UniversityUpdateView.as_view(),
        name="university_update",
    ),
]
from django.urls import path
from . import views


app_name = "universities"

urlpatterns = [
    path("", views.UniversityListView.as_view(), name="list"),
    path("create/", views.UniversityCreateView.as_view(), name="create"),
    path(
        "public/<slug:slug>/",
        views.UniversityDetailView.as_view(),
        name="detail",
    ),
    path(
        "<uuid:pk>/archive/",
        views.UniversityArchiveView.as_view(),
        name="archive",
    ),
    path("<uuid:pk>/", views.UniversityUpdateView.as_view(), name="update"),
]

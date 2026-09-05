from django.urls import path

from . import views

urlpatterns = [
    path("points/", views.public_points, name="public-points"),
    path("categories/", views.public_categories, name="public-categories"),
]

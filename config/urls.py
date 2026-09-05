from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("reports.urls")),
    # TODO: path("media/<int:report_id>/", ...) — прокси фото из OneDrive
]

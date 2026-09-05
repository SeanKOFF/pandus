from django.contrib import admin
from django.urls import include, path

from reports import views as reports_views

urlpatterns = [
    path("", reports_views.map_page, name="map"),
    path("admin/", admin.site.urls),
    path("api/", include("reports.urls")),
    path("media/<int:report_id>/", reports_views.photo, name="report-photo"),
]

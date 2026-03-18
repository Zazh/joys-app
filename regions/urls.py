from django.urls import path

from . import views

app_name = 'regions'

urlpatterns = [
    path('set/', views.SetRegionView.as_view(), name='set_region'),
]

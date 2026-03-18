from django.urls import path

from . import views

app_name = 'qrcodes'

urlpatterns = [
    path('<int:pk>/download/', views.download_qr_zip, name='download_zip'),
]

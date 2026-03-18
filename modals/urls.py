from django.urls import path

from . import views

app_name = 'modals'

urlpatterns = [
    path('<slug:slug>/', views.InteractiveModalDetailView.as_view(), name='modal_detail'),
]

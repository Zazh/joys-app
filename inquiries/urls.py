from django.urls import path

from . import views

app_name = 'inquiries'

urlpatterns = [
    path('<slug:slug>/', views.InquiryFormDetailView.as_view(), name='form_detail'),
    path('<slug:slug>/submit/', views.InquirySubmitView.as_view(), name='form_submit'),
]

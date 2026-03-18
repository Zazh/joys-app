from django.urls import path
from . import views

app_name = 'quiz'

urlpatterns = [
    path('result/', views.QuizResultView.as_view(), name='quiz_result'),
]

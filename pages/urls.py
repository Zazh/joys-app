from django.urls import path

from . import views

app_name = 'pages'

urlpatterns = [
    path('blog/', views.BlogListView.as_view(), name='blog_list'),
    path('blog/<slug:slug>/', views.BlogDetailView.as_view(), name='blog_detail'),
    path('category/<slug:slug>/', views.PageCategoryDetailView.as_view(), name='category_detail'),
    path('<slug:slug>/', views.PageDetailView.as_view(), name='page_detail'),
]

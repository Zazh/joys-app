from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.CatalogListView.as_view(), name='catalog'),
path('<slug:category_slug>/', views.CatalogListView.as_view(), name='category'),
    path('<slug:category_slug>/<slug:product_slug>/', views.ProductDetailView.as_view(), name='product_detail'),
]

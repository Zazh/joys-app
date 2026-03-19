from django.urls import path

from .views.auth import LoginView, LogoutView
from .views.dashboard import DashboardView
from .views.orders import OrderListView, OrderDetailView, OrderStatusUpdateView
from .views.inquiries import InquiryListView, InquiryDetailView, InquiryToggleProcessedView
from .views.qrcodes import (
    QRCodeListView, QRCodeCreateView, QRCodeDetailView,
    QRCodeDeleteView, QRCodeDownloadView,
)
from .views.catalog import (
    ProductListView, ProductEditView, ProductCreateView,
    ProductToggleActiveView, ProductImageUploadView,
    ProductImageDeleteView, ProductImageCoverView,
    ProductSizeCreateView, ProductSizeDeleteView,
    CharacteristicListView, CharacteristicCreateView,
    CharacteristicEditView, CharacteristicDeleteView,
    CategoryListView, CategoryEditView, CategoryCreateView,
)
from .views.pages import (
    ServicePageListView, ServicePageEditView,
    PageListView, PageEditView, PageCreateView,
    BlogPostListView, BlogPostEditView, BlogPostCreateView,
)
from .views.redirects import (
    RedirectListView, RedirectCreateView, RedirectEditView, RedirectDeleteView,
)
from .views.upload import ImageUploadView
from .views.users import (
    UserListView, UserDetailView, UserCreateView, UserEditView, UserToggleActiveView,
)
from .views.emails import EmailLogListView, EmailLogDetailView, EmailLogRetryView
from .views.stock import StockListView, StockUpdateView
from .views.reviews import ReviewListView, ReviewToggleView, ReviewSyncView
from .views.quiz_analytics import QuizAnalyticsView
from .views.homepage import (
    HomepageOverviewView, HeroEditView, HeroCardUploadView, HeroCardUpdateView, HeroCardDeleteView,
    FeatureSlideListView, FeatureSlideEditView, FeatureSlideCreateView, FeatureSlideDeleteView,
    PromoBlockEditView, PromoGalleryUploadView, PromoGalleryDeleteView,
    ModalListView, ModalEditView, ModalStepCreateView, ModalStepDeleteView,
    QuizOverviewView, QuizQuestionSaveView, QuizResultTextSaveView,
    QuizRuleCreateView, QuizRuleDeleteView, QuizBackgroundSaveView,
)

app_name = 'backoffice'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('', DashboardView.as_view(), name='dashboard'),
    path('orders/', OrderListView.as_view(), name='order_list'),
    path('orders/<str:number>/', OrderDetailView.as_view(), name='order_detail'),
    path('orders/<str:number>/status/', OrderStatusUpdateView.as_view(), name='order_status'),
    path('inquiries/', InquiryListView.as_view(), name='inquiry_list'),
    path('inquiries/<int:pk>/', InquiryDetailView.as_view(), name='inquiry_detail'),
    path('inquiries/<int:pk>/toggle/', InquiryToggleProcessedView.as_view(), name='inquiry_toggle'),
    path('qrcodes/', QRCodeListView.as_view(), name='qrcode_list'),
    path('qrcodes/create/', QRCodeCreateView.as_view(), name='qrcode_create'),
    path('qrcodes/<int:pk>/', QRCodeDetailView.as_view(), name='qrcode_detail'),
    path('qrcodes/<int:pk>/delete/', QRCodeDeleteView.as_view(), name='qrcode_delete'),
    path('qrcodes/<int:pk>/download/', QRCodeDownloadView.as_view(), name='qrcode_download'),
    # Каталог
    path('products/', ProductListView.as_view(), name='product_list'),
    path('products/create/', ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/', ProductEditView.as_view(), name='product_edit'),
    path('products/<int:pk>/toggle/', ProductToggleActiveView.as_view(), name='product_toggle_active'),
    path('products/<int:pk>/images/upload/', ProductImageUploadView.as_view(), name='product_image_upload'),
    path('products/<int:pk>/images/delete/', ProductImageDeleteView.as_view(), name='product_image_delete'),
    path('products/<int:pk>/images/cover/', ProductImageCoverView.as_view(), name='product_image_cover'),
    path('products/<int:pk>/sizes/create/', ProductSizeCreateView.as_view(), name='product_size_create'),
    path('products/<int:pk>/sizes/delete/', ProductSizeDeleteView.as_view(), name='product_size_delete'),
    path('characteristics/', CharacteristicListView.as_view(), name='characteristic_list'),
    path('characteristics/create/', CharacteristicCreateView.as_view(), name='characteristic_create'),
    path('characteristics/<int:pk>/', CharacteristicEditView.as_view(), name='characteristic_edit'),
    path('characteristics/<int:pk>/delete/', CharacteristicDeleteView.as_view(), name='characteristic_delete'),
    path('categories/', CategoryListView.as_view(), name='category_list'),
    path('categories/create/', CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/', CategoryEditView.as_view(), name='category_edit'),
    # Страницы
    path('service-pages/', ServicePageListView.as_view(), name='service_page_list'),
    path('service-pages/<int:pk>/', ServicePageEditView.as_view(), name='service_page_edit'),
    # Статические страницы
    path('pages/', PageListView.as_view(), name='page_list'),
    path('pages/create/', PageCreateView.as_view(), name='page_create'),
    path('pages/<int:pk>/', PageEditView.as_view(), name='page_edit'),
    # Блог
    path('blog/', BlogPostListView.as_view(), name='blog_list'),
    path('blog/create/', BlogPostCreateView.as_view(), name='blog_create'),
    path('blog/<int:pk>/', BlogPostEditView.as_view(), name='blog_edit'),
    # Редиректы
    path('redirects/', RedirectListView.as_view(), name='redirect_list'),
    path('redirects/create/', RedirectCreateView.as_view(), name='redirect_create'),
    path('redirects/<int:pk>/', RedirectEditView.as_view(), name='redirect_edit'),
    path('redirects/<int:pk>/delete/', RedirectDeleteView.as_view(), name='redirect_delete'),
    # Главная страница
    path('homepage/', HomepageOverviewView.as_view(), name='homepage_overview'),
    path('homepage/hero/', HeroEditView.as_view(), name='homepage_hero'),
    path('homepage/hero/cards/upload/', HeroCardUploadView.as_view(), name='homepage_hero_card_upload'),
    path('homepage/hero/cards/<int:card_pk>/update/', HeroCardUpdateView.as_view(), name='homepage_hero_card_update'),
    path('homepage/hero/cards/delete/', HeroCardDeleteView.as_view(), name='homepage_hero_card_delete'),
    path('homepage/features/', FeatureSlideListView.as_view(), name='homepage_features'),
    path('homepage/features/create/', FeatureSlideCreateView.as_view(), name='homepage_feature_create'),
    path('homepage/features/<int:pk>/', FeatureSlideEditView.as_view(), name='homepage_feature_edit'),
    path('homepage/features/<int:pk>/delete/', FeatureSlideDeleteView.as_view(), name='homepage_feature_delete'),
    path('homepage/promo/<int:pk>/', PromoBlockEditView.as_view(), name='homepage_promo_edit'),
    path('homepage/promo/<int:pk>/gallery/upload/', PromoGalleryUploadView.as_view(), name='homepage_promo_gallery_upload'),
    path('homepage/promo/<int:pk>/gallery/delete/', PromoGalleryDeleteView.as_view(), name='homepage_promo_gallery_delete'),
    # Модалки (отдельный раздел)
    path('modals/', ModalListView.as_view(), name='modal_list'),
    path('modals/<int:pk>/', ModalEditView.as_view(), name='modal_edit'),
    path('modals/<int:pk>/steps/create/', ModalStepCreateView.as_view(), name='modal_step_create'),
    path('modals/<int:pk>/steps/<int:step_pk>/delete/', ModalStepDeleteView.as_view(), name='modal_step_delete'),
    # Квиз
    path('quiz/', QuizOverviewView.as_view(), name='quiz_overview'),
    path('quiz/analytics/', QuizAnalyticsView.as_view(), name='quiz_analytics'),
    path('quiz/questions/save/', QuizQuestionSaveView.as_view(), name='quiz_questions_save'),
    path('quiz/result-text/save/', QuizResultTextSaveView.as_view(), name='quiz_result_text_save'),
    path('quiz/rules/create/', QuizRuleCreateView.as_view(), name='quiz_rule_create'),
    path('quiz/rules/<int:pk>/delete/', QuizRuleDeleteView.as_view(), name='quiz_rule_delete'),
    path('quiz/backgrounds/save/', QuizBackgroundSaveView.as_view(), name='quiz_backgrounds_save'),
    # Пользователи
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/create/', UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    path('users/<int:pk>/edit/', UserEditView.as_view(), name='user_edit'),
    path('users/<int:pk>/toggle-active/', UserToggleActiveView.as_view(), name='user_toggle_active'),
    # Логи писем
    path('emails/', EmailLogListView.as_view(), name='email_log_list'),
    path('emails/<int:pk>/', EmailLogDetailView.as_view(), name='email_log_detail'),
    path('emails/<int:pk>/retry/', EmailLogRetryView.as_view(), name='email_log_retry'),
    # Склад
    path('stock/', StockListView.as_view(), name='stock_list'),
    path('stock/update/', StockUpdateView.as_view(), name='stock_update'),
    # Отзывы
    path('reviews/', ReviewListView.as_view(), name='review_list'),
    path('reviews/<int:pk>/toggle/', ReviewToggleView.as_view(), name='review_toggle'),
    path('reviews/sync/', ReviewSyncView.as_view(), name='review_sync'),
    # Загрузка
    path('upload/image/', ImageUploadView.as_view(), name='upload_image'),
]

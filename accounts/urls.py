# accounts/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserProfileViewSet, TransactionViewSet
from rest_framework.urlpatterns import format_suffix_patterns

router = DefaultRouter()
router.register(r'profile', UserProfileViewSet, basename='profile')
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    # Routes standards
    path('', include(router.urls)),
]
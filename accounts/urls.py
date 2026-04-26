# accounts/urls.py
from django.urls import path
from .views import UserProfileViewSet, TransactionViewSet

# Définir les URLs manuellement sans utiliser DefaultRouter
urlpatterns = [
    # Profile
    path('profile/', UserProfileViewSet.as_view({'get': 'list', 'post': 'create'}), name='profile-list'),
    path('profile/me/', UserProfileViewSet.as_view({'get': 'me'}), name='profile-me'),
    path('profile/recharge/', UserProfileViewSet.as_view({'post': 'recharge'}), name='profile-recharge'),
    path('profile/subscribe/', UserProfileViewSet.as_view({'post': 'subscribe'}), name='profile-subscribe'),
    path('profile/buy_book/', UserProfileViewSet.as_view({'post': 'buy_book'}), name='profile-buy-book'),
    path('profile/my_books/', UserProfileViewSet.as_view({'get': 'my_books'}), name='profile-my-books'),
    path('profile/check_access/', UserProfileViewSet.as_view({'get': 'check_access'}), name='profile-check-access'),
    path('profile/transactions/', UserProfileViewSet.as_view({'get': 'transactions'}), name='profile-transactions'),
    
    # Transactions
    path('transactions/', TransactionViewSet.as_view({'get': 'list'}), name='transaction-list'),
    path('transactions/<int:pk>/', TransactionViewSet.as_view({'get': 'retrieve'}), name='transaction-detail'),
]
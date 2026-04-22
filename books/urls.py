# books/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BookViewSet, CategoryViewSet, 
    proxy_cover_image, proxy_epub_download, stream_epub
)

router = DefaultRouter()
router.register(r'books', BookViewSet, basename='book')
router.register(r'categories', CategoryViewSet, basename='category')

urlpatterns = [
    path('', include(router.urls)),
    path('books/<int:book_id>/cover/', proxy_cover_image, name='book-cover'),
    path('books/<int:book_id>/download/', proxy_epub_download, name='book-download'),
    path('books/<int:book_id>/stream/', stream_epub, name='book-stream'),
]
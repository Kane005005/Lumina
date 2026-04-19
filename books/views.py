# books/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Book, Category
from .serializers import BookSerializer, CategorySerializer
from django.db import models
import requests
import hashlib
import os
from django.http import HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_page
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from rest_framework import viewsets
from .models import Book, Category
from .serializers import BookSerializer, CategorySerializer

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.filter(is_active=True)
    serializer_class = BookSerializer
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.downloads_count += 1
        instance.save(update_fields=['downloads_count'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        recent_books = self.get_queryset()[:10]
        serializer = self.get_serializer(recent_books, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if query:
            books = self.get_queryset().filter(
                models.Q(title__icontains=query) | 
                models.Q(author__icontains=query)
            )
            serializer = self.get_serializer(books, many=True)
            return Response(serializer.data)
        return Response([])


@csrf_exempt
@cache_page(60 * 60 * 24)
def proxy_cover_image(request, book_id):
    book = get_object_or_404(Book, id=book_id, is_active=True)
    
    cover_id = book.get_cover_id()
    
    if not cover_id:
        return serve_placeholder_image()
    
    # Thumbnail Google Drive
    thumbnail_url = f"https://drive.google.com/thumbnail?sz=w800&id={cover_id}"
    
    try:
        response = requests.get(thumbnail_url, timeout=10)
        if response.status_code == 200:
            return HttpResponse(
                response.content,
                content_type='image/jpeg'
            )
    except Exception as e:
        print(f"Erreur proxy : {e}")
    
    return serve_placeholder_image()

def serve_placeholder_image():
    """Sert une image placeholder."""
    # Créer une image SVG simple
    svg_content = '''
    <svg width="400" height="600" xmlns="http://www.w3.org/2000/svg">
        <rect width="400" height="600" fill="#059669"/>
        <text x="200" y="300" font-family="Arial" font-size="20" fill="white" text-anchor="middle">
            📚 LuminaReads
        </text>
        <text x="200" y="340" font-family="Arial" font-size="14" fill="#a7f3d0" text-anchor="middle">
            Couverture non disponible
        </text>
    </svg>
    '''
    return HttpResponse(svg_content, content_type='image/svg+xml')


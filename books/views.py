# books/views.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.http import Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from .models import Book, Category
from .serializers import BookSerializer, CategorySerializer
import requests
import os


class StandardResultsSetPagination(PageNumberPagination):
    """Pagination standard pour les listes de livres."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des catégories."""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class BookViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des livres avec actions personnalisées."""
    queryset = Book.objects.filter(is_active=True)
    serializer_class = BookSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'author', 'description']
    ordering_fields = ['created_at', 'downloads_count', 'title']
    ordering = ['-created_at']
    
    def retrieve(self, request, *args, **kwargs):
        """Récupère un livre et incrémente le compteur de téléchargements."""
        instance = self.get_object()
        instance.downloads_count += 1
        instance.save(update_fields=['downloads_count'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        Récupère les livres récemment ajoutés.
        Endpoint: /api/books/recent/
        """
        recent_books = self.get_queryset().order_by('-created_at')[:8]
        serializer = self.get_serializer(recent_books, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """
        Récupère les livres mis en avant pour le carrousel.
        Endpoint: /api/books/featured/
        """
        # Si le champ is_featured n'existe pas encore, on peut utiliser une logique alternative
        try:
            featured_books = self.get_queryset().filter(is_featured=True).order_by('-featured_order', '-created_at')[:5]
        except:
            # Fallback: prendre les livres les plus populaires ou récents
            featured_books = self.get_queryset().order_by('-downloads_count', '-created_at')[:5]
        
        serializer = self.get_serializer(featured_books, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Recherche avancée avec filtres et tri.
        Endpoint: /api/books/search/?q=terme&category=1&ordering=-downloads_count
        """
        queryset = self.get_queryset()
        
        # 1. Recherche textuelle
        query = request.query_params.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(author__icontains=query) |
                Q(description__icontains=query)
            ).distinct()
        
        # 2. Filtre par catégorie
        category_id = request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # 3. Filtre par auteur (optionnel)
        author = request.query_params.get('author')
        if author:
            queryset = queryset.filter(author__icontains=author)
        
        # 4. Tri
        ordering = request.query_params.get('ordering', '-created_at')
        allowed_ordering = ['created_at', '-created_at', 'downloads_count', '-downloads_count', 'title', '-title']
        if ordering in allowed_ordering:
            queryset = queryset.order_by(ordering)
        
        # 5. Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'count': queryset.count(),
            'query': query,
            'filters_applied': {
                'category': category_id,
                'author': author,
                'ordering': ordering
            }
        })
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """
        Filtre les livres par catégorie.
        Endpoint: /api/books/by_category/?category_id=1
        """
        category_id = request.query_params.get('category_id')
        if category_id:
            books = self.get_queryset().filter(category_id=category_id)
            
            page = self.paginate_queryset(books)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(books, many=True)
            return Response(serializer.data)
        return Response([])
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """
        Récupère toutes les catégories avec le nombre de livres.
        Endpoint: /api/books/categories/
        """
        categories = Category.objects.annotate(
            book_count=Count('book', filter=Q(book__is_active=True))
        ).filter(book_count__gt=0)
        
        data = [{
            'id': cat.id,
            'name': cat.name,
            'slug': cat.slug,
            'book_count': cat.book_count
        } for cat in categories]
        
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def authors(self, request):
        """
        Récupère la liste des auteurs uniques.
        Endpoint: /api/books/authors/
        """
        authors = Book.objects.filter(is_active=True).exclude(
            author__isnull=True
        ).exclude(author='').values_list('author', flat=True).distinct().order_by('author')
        
        return Response(list(authors))


# ==================== PROXY D'IMAGES ====================

@csrf_exempt
@cache_page(60 * 60 * 24)  # Cache de 24 heures
def proxy_cover_image(request, book_id):
    """
    Proxy pour servir les images de couverture depuis Google Drive.
    Évite les problèmes CORS et met en cache les images.
    """
    book = get_object_or_404(Book, id=book_id, is_active=True)
    
    cover_id = book.get_cover_id()
    
    if not cover_id:
        return serve_placeholder_image(book.title if book else "Livre")
    
    # Thumbnail Google Drive avec meilleure qualité
    thumbnail_url = f"https://drive.google.com/thumbnail?sz=w800&id={cover_id}"
    
    # Tentative de récupération depuis le cache
    cache_key = f"cover_image_{cover_id}"
    cached_image = cache.get(cache_key)
    
    if cached_image:
        return HttpResponse(cached_image, content_type='image/jpeg')
    
    try:
        response = requests.get(thumbnail_url, timeout=10)
        if response.status_code == 200:
            # Mise en cache de l'image
            cache.set(cache_key, response.content, 60 * 60 * 24)  # 24 heures
            return HttpResponse(
                response.content,
                content_type='image/jpeg'
            )
    except Exception as e:
        print(f"Erreur proxy pour le livre {book_id}: {e}")
    
    return serve_placeholder_image(book.title)


def serve_placeholder_image(title="Livre"):
    """Sert une image placeholder SVG élégante."""
    # Tronquer le titre si trop long
    display_title = title[:30] + "..." if len(title) > 30 else title
    
    svg_content = f'''
    <svg width="400" height="600" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#059669;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#047857;stop-opacity:1" />
            </linearGradient>
            <filter id="shadow">
                <feDropShadow dx="2" dy="2" stdDeviation="3" flood-opacity="0.3"/>
            </filter>
        </defs>
        
        <rect width="400" height="600" fill="url(#grad)" rx="8"/>
        
        <!-- Motif décoratif -->
        <circle cx="200" cy="150" r="60" fill="none" stroke="#34d399" stroke-width="1" opacity="0.3"/>
        <circle cx="200" cy="150" r="80" fill="none" stroke="#34d399" stroke-width="0.5" opacity="0.2"/>
        
        <!-- Icône livre -->
        <text x="200" y="180" font-family="Arial, sans-serif" font-size="64" fill="white" text-anchor="middle" opacity="0.9">
            📚
        </text>
        
        <!-- Titre du livre -->
        <text x="200" y="280" font-family="Georgia, serif" font-size="18" fill="white" text-anchor="middle" font-weight="bold" filter="url(#shadow)">
            {display_title}
        </text>
        
        <!-- Sous-titre -->
        <text x="200" y="320" font-family="Arial, sans-serif" font-size="13" fill="#a7f3d0" text-anchor="middle" opacity="0.9">
            LuminaReads
        </text>
        
        <!-- Message placeholder -->
        <text x="200" y="500" font-family="Arial, sans-serif" font-size="12" fill="#6ee7b7" text-anchor="middle" opacity="0.7">
            Couverture non disponible
        </text>
        
        <!-- Ligne décorative -->
        <line x1="150" y1="520" x2="250" y2="520" stroke="#34d399" stroke-width="1" opacity="0.3"/>
    </svg>
    '''
    return HttpResponse(svg_content, content_type='image/svg+xml')


# ==================== TÉLÉCHARGEMENT DE FICHIERS ====================

@csrf_exempt
def download_book(request, book_id):
    """
    Endpoint pour télécharger un livre.
    Redirige vers l'URL Google Drive ou sert le fichier local.
    """
    book = get_object_or_404(Book, id=book_id, is_active=True)
    
    # Incrémenter le compteur de téléchargements
    book.downloads_count += 1
    book.save(update_fields=['downloads_count'])
    
    # Vérifier si le livre a un fichier associé
    if book.epub_file_url:
        # Redirection vers Google Drive ou autre stockage cloud
        return HttpResponse(book.epub_file_url, status=302)
    elif book.file:
        # Servir le fichier local si disponible
        response = HttpResponse(book.file, content_type='application/epub+zip')
        response['Content-Disposition'] = f'attachment; filename="{book.title}.epub"'
        return response
    else:
        raise Http404("Fichier non disponible pour ce livre")

# books/views.py - ajouter cette vue
import requests
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def proxy_epub_download(request, book_id):
    """
    Proxy pour télécharger les fichiers EPUB depuis Google Drive.
    Évite les problèmes CORS.
    """
    book = get_object_or_404(Book, id=book_id, is_active=True)
    
    # Incrémenter le compteur de téléchargements
    book.downloads_count += 1
    book.save(update_fields=['downloads_count'])
    
    # Récupérer l'ID ou l'URL
    epub_id = book.get_epub_id()
    epub_url = book.epub_file_url
    
    if epub_id:
        download_url = f"https://drive.google.com/uc?export=download&id={epub_id}"
    elif epub_url:
        download_url = epub_url
    else:
        return HttpResponse("Fichier non disponible", status=404)
    
    try:
        # Télécharger le fichier depuis Google Drive
        response = requests.get(download_url, stream=True, timeout=30)
        
        if response.status_code == 200:
            # Créer une réponse streaming
            django_response = StreamingHttpResponse(
                response.iter_content(chunk_size=8192),
                content_type='application/epub+zip'
            )
            
            # Nettoyer le nom du fichier
            filename = f"{book.title.replace(' ', '_')[:50]}.epub"
            filename = ''.join(c for c in filename if c.isalnum() or c in '._-')
            
            django_response['Content-Disposition'] = f'attachment; filename="{filename}"'
            django_response['Access-Control-Allow-Origin'] = '*'
            django_response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            django_response['Access-Control-Allow-Headers'] = '*'
            
            return django_response
        else:
            return HttpResponse(
                f"Erreur lors du téléchargement: {response.status_code}",
                status=response.status_code
            )
            
    except Exception as e:
        print(f"Erreur proxy EPUB: {e}")
        return HttpResponse(f"Erreur serveur: {str(e)}", status=500)

@csrf_exempt
def stream_epub(request, book_id):
    """
    Stream l'EPUB pour la lecture en ligne (sans téléchargement forcé).
    """
    book = get_object_or_404(Book, id=book_id, is_active=True)
    
    epub_id = book.get_epub_id()
    epub_url = book.epub_file_url
    
    if epub_id:
        download_url = f"https://drive.google.com/uc?export=download&id={epub_id}"
    elif epub_url:
        download_url = epub_url
    else:
        return HttpResponse("Fichier non disponible", status=404)
    
    try:
        response = requests.get(download_url, stream=True, timeout=30)
        
        if response.status_code == 200:
            django_response = StreamingHttpResponse(
                response.iter_content(chunk_size=8192),
                content_type='application/epub+zip'
            )
            django_response['Access-Control-Allow-Origin'] = '*'
            return django_response
        else:
            return HttpResponse(status=response.status_code)
            
    except Exception as e:
        print(f"Erreur stream EPUB: {e}")
        return HttpResponse(status=500)
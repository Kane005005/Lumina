# books/models.py
from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    
    class Meta:
        verbose_name_plural = "Categories"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name

# books/models.py
import re
from django.db import models

class Book(models.Model):
    title = models.CharField(max_length=500)
    author = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    # IDs stockés (pour les nouveaux livres)
    cover_image_id = models.CharField(max_length=255, blank=True, null=True)
    epub_file_id = models.CharField(max_length=255, blank=True, null=True)
    
    # URLs complètes (pour compatibilité)
    cover_image_url = models.CharField(max_length=500, blank=True, null=True)
    epub_file_url = models.CharField(max_length=500, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    downloads_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def extract_id_from_url(self, url):
        """Extrait l'ID Google Drive d'une URL."""
        if not url:
            return None
        
        # Pattern pour les URLs Google Drive
        patterns = [
            r'[?&]id=([^&]+)',           # ?id=XXX ou &id=XXX
            r'/d/([^/]+)',               # /d/XXX/
            r'/folders/([^/?]+)',         # /folders/XXX
            r'thumbnail.*id=([^&]+)',     # thumbnail?id=XXX
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_cover_id(self):
        """Récupère l'ID de couverture (stocké ou extrait)."""
        if self.cover_image_id:
            return self.cover_image_id
        return self.extract_id_from_url(self.cover_image_url)
    
    def get_epub_id(self):
        """Récupère l'ID EPUB (stocké ou extrait)."""
        if self.epub_file_id:
            return self.epub_file_id
        return self.extract_id_from_url(self.epub_file_url)
    
    def get_cover_proxy_url(self):
        """URL du proxy Django pour la couverture."""
        cover_id = self.get_cover_id()
        if cover_id:
            return f"/api/books/{self.id}/cover/"
        return None
    
    def get_download_url(self):
        """URL de téléchargement direct."""
        epub_id = self.get_epub_id()
        if epub_id:
            return f"https://drive.google.com/uc?export=download&id={epub_id}"
        return self.epub_file_url
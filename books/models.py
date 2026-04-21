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

class Book(models.Model):
    title = models.CharField(max_length=500)
    author = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    # IDs Google Drive
    cover_image_id = models.CharField(max_length=255, blank=True, null=True)
    epub_file_id = models.CharField(max_length=255, blank=True, null=True)
    
    # URLs
    cover_image_url = models.CharField(max_length=500, blank=True, null=True)
    epub_file_url = models.CharField(max_length=500, blank=True, null=True)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    downloads_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # 🆕 NOUVEAU : Livre mis en avant
    is_featured = models.BooleanField(default=False, verbose_name="Mis en avant")
    featured_order = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")
    
    # Relations
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-is_featured', '-featured_order', '-created_at']
        verbose_name = "Livre"
        verbose_name_plural = "Livres"
    
    def __str__(self):
        return self.title
    
    def get_cover_id(self):
        if self.cover_image_id:
            return self.cover_image_id
        if self.cover_image_url:
            import re
            match = re.search(r'[?&]id=([^&]+)', self.cover_image_url)
            if match:
                return match.group(1)
        return None
    
    def get_cover_proxy_url(self):
        cover_id = self.get_cover_id()
        if cover_id:
            return f"/api/books/{self.id}/cover/"
        return None
    
    def get_download_url(self):
        if self.epub_file_id:
            return f"https://drive.google.com/uc?export=download&id={self.epub_file_id}"
        return self.epub_file_url
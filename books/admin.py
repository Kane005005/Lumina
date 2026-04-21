# books/admin.py
from django.contrib import admin
from .models import Book, Category

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'is_featured', 'featured_order', 'downloads_count', 'created_at']
    list_filter = ['is_featured', 'category', 'created_at']
    list_editable = ['is_featured', 'featured_order']
    search_fields = ['title', 'author', 'description']
    readonly_fields = ['downloads_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('title', 'author', 'description', 'category')
        }),
        ('Mise en avant', {
            'fields': ('is_featured', 'featured_order'),
            'description': 'Les livres mis en avant apparaissent dans le carousel de la page d\'accueil.'
        }),
        ('Google Drive', {
            'fields': ('cover_image_id', 'epub_file_id', 'cover_image_url', 'epub_file_url'),
            'classes': ('collapse',)
        }),
        ('Statistiques', {
            'fields': ('downloads_count', 'created_at', 'updated_at', 'is_active'),
        }),
    )
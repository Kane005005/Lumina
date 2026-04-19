
from django.contrib import admin
from .models import Category, Book

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'is_active', 'created_at', 'downloads_count')
    list_filter = ('is_active', 'category', 'created_at')
    search_fields = ('title', 'author')
    readonly_fields = ('created_at', 'updated_at', 'downloads_count')
    ordering = ('-created_at',)

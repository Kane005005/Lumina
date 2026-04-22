# books/serializers.py
from rest_framework import serializers
from .models import Book, Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

class BookSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    cover_url = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    stream_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Book
        fields = [
            'id', 'title', 'author', 'description',
            'cover_url', 'download_url', 'stream_url',
            'cover_image_url', 'epub_file_url',
            'cover_image_id', 'epub_file_id',
            'category', 'category_name',
            'created_at', 'downloads_count', 'is_active',
            'is_featured', 'featured_order'
        ]
        read_only_fields = ['created_at', 'downloads_count']
    
    def get_cover_url(self, obj):
        return obj.get_cover_proxy_url()
    
    def get_download_url(self, obj):
        return obj.get_download_url()
    
    def get_stream_url(self, obj):
        return obj.get_stream_url()
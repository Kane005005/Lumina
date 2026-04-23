# books/epub_service.py
import os
import tempfile
import requests
from ebooklib import epub
from bs4 import BeautifulSoup
from django.core.cache import cache

class EpubReaderService:
    """Service pour lire et servir des fichiers EPUB page par page."""
    
    def __init__(self, book):
        self.book = book
        self.epub_book = None
        self.spine_items = []
        self._loaded = False
    
    def _download_epub(self):
        """Télécharge l'EPUB depuis Google Drive."""
        epub_url = self.book.epub_file_url
        
        if not epub_url:
            # Essayer de construire l'URL avec l'ID
            epub_id = self.book.get_epub_id()
            if epub_id:
                epub_url = f"https://drive.google.com/uc?export=download&id={epub_id}"
            else:
                raise ValueError("Aucune URL ou ID EPUB disponible")
        
        # Télécharger dans un fichier temporaire
        response = requests.get(epub_url, timeout=30, stream=True)
        response.raise_for_status()
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.epub')
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        temp_file.close()
        
        return temp_file.name
    
    def load(self):
        """Charge l'EPUB en mémoire."""
        if self._loaded:
            return
        
        # Vérifier le cache d'abord
        cache_key = f"epub_parsed_{self.book.id}"
        cached = cache.get(cache_key)
        
        if cached:
            self.spine_items = cached.get('spine_items', [])
            self._loaded = True
            return
        
        # Télécharger et parser
        epub_path = self._download_epub()
        
        try:
            self.epub_book = epub.read_epub(epub_path)
            
            # Extraire les items dans l'ordre de lecture (spine)
            self.spine_items = []
            for item in self.epub_book.spine:
                item_obj = self.epub_book.get_item_with_id(item[0])
                if item_obj and item_obj.get_type() == 9:  # ITEM_DOCUMENT
                    self.spine_items.append(item_obj)
            
            self._loaded = True
            
            # Mettre en cache pour 1 heure
            cache.set(cache_key, {
                'spine_items': [item.get_id() for item in self.spine_items]
            }, 3600)
            
        finally:
            os.unlink(epub_path)
    
    def get_total_pages(self):
        """Retourne le nombre total de pages."""
        self.load()
        return len(self.spine_items)
    
    def get_page(self, page_number):
        """
        Retourne le contenu HTML de la page demandée.
        
        Args:
            page_number: Index de la page (1-based)
            
        Returns:
            dict: {
                'html': contenu HTML nettoyé,
                'page': page_number,
                'total': nombre total de pages,
                'has_prev': bool,
                'has_next': bool
            }
        """
        self.load()
        
        # Convertir en 0-based
        index = page_number - 1
        
        if index < 0 or index >= len(self.spine_items):
            raise ValueError(f"Page {page_number} hors limites (1-{len(self.spine_items)})")
        
        item = self.spine_items[index]
        content = item.get_content().decode('utf-8', errors='ignore')
        
        # Nettoyer le HTML avec BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        
        # Supprimer les scripts et styles
        for tag in soup(['script', 'style', 'link', 'meta']):
            tag.decompose()
        
        # Extraire le body
        body = soup.find('body')
        if body:
            html_content = str(body)
        else:
            html_content = str(soup)
        
        return {
            'html': html_content,
            'page': page_number,
            'total': len(self.spine_items),
            'has_prev': page_number > 1,
            'has_next': page_number < len(self.spine_items)
        }
    
    def get_metadata(self):
        """Retourne les métadonnées du livre."""
        self.load()
        
        if not self.epub_book:
            return {}
        
        metadata = {}
        for key, values in self.epub_book.metadata.items():
            if values:
                metadata[key] = values[0][0] if values[0] else None
        
        return metadata
    
    def get_toc(self):
        """Retourne la table des matières."""
        self.load()
        
        if not self.epub_book:
            return []
        
        toc = []
        for item in self.epub_book.toc:
            if isinstance(item, tuple):
                toc.append({
                    'title': item[0].title if hasattr(item[0], 'title') else str(item[0]),
                    'href': item[1] if len(item) > 1 else None
                })
        
        return toc
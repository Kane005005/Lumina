# books/epub_service.py - VERSION CORRIGÉE
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
            epub_id = self.book.get_epub_id()
            if epub_id:
                epub_url = f"https://drive.google.com/uc?export=download&id={epub_id}"
            else:
                raise ValueError("Aucune URL ou ID EPUB disponible")
        
        print(f"📥 Téléchargement EPUB: {epub_url}")
        
        response = requests.get(epub_url, timeout=60, stream=True)
        response.raise_for_status()
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.epub')
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        temp_file.close()
        
        print(f"✅ EPUB téléchargé: {temp_file.name}")
        return temp_file.name
    
    def load(self):
        """Charge l'EPUB en mémoire."""
        if self._loaded:
            return
        
        cache_key = f"epub_parsed_{self.book.id}"
        cached = cache.get(cache_key)
        
        if cached:
            print(f"📦 EPUB chargé depuis le cache")
            self.spine_items = cached.get('spine_items', [])
            self._loaded = True
            return
        
        epub_path = self._download_epub()
        
        try:
            print(f"📖 Parsing EPUB...")
            self.epub_book = epub.read_epub(epub_path)
            
            # Extraire les items dans l'ordre de lecture (spine)
            self.spine_items = []
            
            # Le spine contient des tuples (id, linear)
            for item_id, linear in self.epub_book.spine:
                # Récupérer l'objet à partir de l'ID
                item_obj = self.epub_book.get_item_with_id(item_id)
                
                if item_obj:
                    # Vérifier le type (9 = document)
                    if item_obj.get_type() == 9:
                        self.spine_items.append({
                            'id': item_id,
                            'href': item_obj.get_name(),
                            'item': item_obj
                        })
                        print(f"  ✅ Page {len(self.spine_items)}: {item_id}")
                else:
                    print(f"  ⚠️ Item non trouvé: {item_id}")
            
            print(f"📚 Total pages: {len(self.spine_items)}")
            
            self._loaded = True
            
            # Mettre en cache les IDs (pas les objets, non sérialisables)
            cache.set(cache_key, {
                'spine_items': [
                    {'id': item['id'], 'href': item['href']} 
                    for item in self.spine_items
                ]
            }, 3600)
            
        except Exception as e:
            print(f"❌ Erreur parsing EPUB: {e}")
            raise
        finally:
            os.unlink(epub_path)
            print(f"🧹 Fichier temporaire supprimé")
    
    def get_total_pages(self):
        """Retourne le nombre total de pages."""
        self.load()
        return len(self.spine_items)
    
    def get_page(self, page_number):
        """
        Retourne le contenu HTML de la page demandée.
        """
        self.load()
        
        index = page_number - 1
        
        if index < 0 or index >= len(self.spine_items):
            raise ValueError(f"Page {page_number} hors limites (1-{len(self.spine_items)})")
        
        item_data = self.spine_items[index]
        
        # Si on a chargé depuis le cache, il faut recharger l'objet
        if 'item' not in item_data:
            # Recharger l'EPUB pour cette requête
            epub_path = self._download_epub()
            try:
                temp_book = epub.read_epub(epub_path)
                item_obj = temp_book.get_item_with_id(item_data['id'])
                if item_obj:
                    content = item_obj.get_content().decode('utf-8', errors='ignore')
                else:
                    raise ValueError(f"Impossible de trouver l'item {item_data['id']}")
            finally:
                os.unlink(epub_path)
        else:
            item_obj = item_data['item']
            content = item_obj.get_content().decode('utf-8', errors='ignore')
        
        # Nettoyer le HTML
        soup = BeautifulSoup(content, 'html.parser')
        
        for tag in soup(['script', 'style', 'link', 'meta']):
            tag.decompose()
        
        body = soup.find('body')
        html_content = str(body) if body else str(soup)
        
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
            # Recharger pour les métadonnées
            epub_path = self._download_epub()
            try:
                temp_book = epub.read_epub(epub_path)
                metadata = {}
                for key, values in temp_book.metadata.items():
                    if values:
                        metadata[key] = values[0][0] if values[0] else None
                return metadata
            finally:
                os.unlink(epub_path)
        
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
            if isinstance(item, tuple) and len(item) >= 2:
                toc.append({
                    'title': str(item[0]) if item[0] else 'Sans titre',
                    'href': item[1]
                })
            elif hasattr(item, 'title'):
                toc.append({
                    'title': item.title,
                    'href': item.href if hasattr(item, 'href') else None
                })
        
        return toc
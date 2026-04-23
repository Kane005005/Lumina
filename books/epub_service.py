# books/epub_service.py
import os
import tempfile
import requests
import re
from ebooklib import epub
from bs4 import BeautifulSoup
from django.core.cache import cache

class EpubReaderService:
    """Service pour lire et servir des fichiers EPUB avec pagination intelligente."""
    
    # Constantes de pagination
    CHARS_PER_PAGE = 2000  # Nombre de caractères par page
    PARAGRAPHS_PER_PAGE = 5  # Nombre de paragraphes par page (fallback)
    
    def __init__(self, book):
        self.book = book
        self.epub_book = None
        self.pages = []  # Liste des pages (texte HTML formaté)
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
        
        print(f"📥 Téléchargement EPUB: {epub_url[:100]}...")
        
        response = requests.get(epub_url, timeout=60, stream=True)
        response.raise_for_status()
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.epub')
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        temp_file.close()
        
        print(f"✅ EPUB téléchargé: {temp_file.name}")
        return temp_file.name
    
    def _extract_text_from_html(self, html_content):
        """Extrait le texte formaté du HTML, en préservant les paragraphes."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Supprimer les éléments non désirés
        for tag in soup(['script', 'style', 'link', 'meta', 'nav', 'header', 'footer']):
            tag.decompose()
        
        # Liste pour stocker les éléments formatés
        formatted_elements = []
        
        # Parcourir tous les éléments pertinents
        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'div']):
            # Ignorer les éléments vides
            text = element.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            
            # Conserver le HTML pour le style
            tag_name = element.name
            
            if tag_name.startswith('h'):
                level = tag_name[1]
                formatted_elements.append({
                    'type': 'heading',
                    'level': level,
                    'html': str(element),
                    'text': text,
                    'length': len(text)
                })
            elif tag_name == 'blockquote':
                formatted_elements.append({
                    'type': 'blockquote',
                    'html': str(element),
                    'text': text,
                    'length': len(text)
                })
            elif tag_name == 'pre':
                formatted_elements.append({
                    'type': 'pre',
                    'html': str(element),
                    'text': text,
                    'length': len(text)
                })
            else:
                # Paragraphe normal
                formatted_elements.append({
                    'type': 'paragraph',
                    'html': str(element),
                    'text': text,
                    'length': len(text)
                })
        
        return formatted_elements
    
    def _paginate_elements(self, elements):
        """Découpe une liste d'éléments en pages."""
        pages = []
        current_page = []
        current_char_count = 0
        current_para_count = 0
        
        for element in elements:
            # Si c'est un titre, on commence une nouvelle page (sauf si page vide)
            if element['type'] == 'heading' and current_page:
                pages.append(current_page)
                current_page = []
                current_char_count = 0
                current_para_count = 0
            
            # Ajouter l'élément
            current_page.append(element)
            current_char_count += element['length']
            current_para_count += 1
            
            # Vérifier si on doit créer une nouvelle page
            if (current_char_count >= self.CHARS_PER_PAGE or 
                current_para_count >= self.PARAGRAPHS_PER_PAGE):
                
                # Ne pas couper au milieu d'un dialogue (optionnel)
                pages.append(current_page)
                current_page = []
                current_char_count = 0
                current_para_count = 0
        
        # Ajouter la dernière page si non vide
        if current_page:
            pages.append(current_page)
        
        return pages
    
    def _render_page(self, page_elements):
        """Rend une page en HTML."""
        html_parts = []
        
        for element in page_elements:
            # Nettoyer légèrement le HTML
            html = element['html']
            
            # Ajouter des classes pour le style
            if element['type'] == 'heading':
                level = element['level']
                html = html.replace(f'<h{level}', f'<h{level} class="reader-heading"')
            elif element['type'] == 'paragraph':
                html = html.replace('<p', '<p class="reader-paragraph"')
            elif element['type'] == 'blockquote':
                html = html.replace('<blockquote', '<blockquote class="reader-blockquote"')
            elif element['type'] == 'pre':
                html = html.replace('<pre', '<pre class="reader-pre"')
            
            html_parts.append(html)
        
        return '\n'.join(html_parts)
    
    def load(self):
        """Charge l'EPUB et le pagine."""
        if self._loaded:
            return
        
        cache_key = f"epub_paginated_{self.book.id}"
        cached = cache.get(cache_key)
        
        if cached:
            print(f"📦 EPUB chargé depuis le cache ({len(cached)} pages)")
            self.pages = cached
            self._loaded = True
            return
        
        epub_path = self._download_epub()
        
        try:
            print(f"📖 Parsing et pagination de l'EPUB...")
            self.epub_book = epub.read_epub(epub_path)
            
            all_elements = []
            
            # Extraire le contenu de chaque document dans l'ordre du spine
            for item_id, linear in self.epub_book.spine:
                item_obj = self.epub_book.get_item_with_id(item_id)
                
                if item_obj and item_obj.get_type() == 9:  # ITEM_DOCUMENT
                    try:
                        content = item_obj.get_content().decode('utf-8', errors='ignore')
                        elements = self._extract_text_from_html(content)
                        all_elements.extend(elements)
                        print(f"  ✅ Section: {item_id} ({len(elements)} éléments)")
                    except Exception as e:
                        print(f"  ⚠️ Erreur section {item_id}: {e}")
            
            print(f"📚 Total éléments extraits: {len(all_elements)}")
            
            # Paginer les éléments
            raw_pages = self._paginate_elements(all_elements)
            
            # Rendre chaque page en HTML
            self.pages = []
            for i, page_elements in enumerate(raw_pages):
                page_html = self._render_page(page_elements)
                char_count = sum(el['length'] for el in page_elements)
                para_count = len(page_elements)
                
                self.pages.append({
                    'html': page_html,
                    'char_count': char_count,
                    'para_count': para_count,
                    'page_number': i + 1
                })
            
            print(f"📖 Total pages générées: {len(self.pages)}")
            
            self._loaded = True
            
            # Mettre en cache (1 heure)
            cache.set(cache_key, self.pages, 3600)
            
        except Exception as e:
            print(f"❌ Erreur parsing EPUB: {e}")
            raise
        finally:
            os.unlink(epub_path)
            print(f"🧹 Fichier temporaire supprimé")
    
    def get_total_pages(self):
        """Retourne le nombre total de pages."""
        self.load()
        return len(self.pages)
    
    def get_page(self, page_number):
        """
        Retourne le contenu HTML de la page demandée.
        """
        self.load()
        
        index = page_number - 1
        
        if index < 0 or index >= len(self.pages):
            raise ValueError(f"Page {page_number} hors limites (1-{len(self.pages)})")
        
        page_data = self.pages[index]
        
        # Ajouter des métadonnées de page
        return {
            'html': page_data['html'],
            'page': page_number,
            'total': len(self.pages),
            'char_count': page_data['char_count'],
            'para_count': page_data['para_count'],
            'has_prev': page_number > 1,
            'has_next': page_number < len(self.pages),
            'progress': round((page_number / len(self.pages)) * 100, 1)
        }
    
    def get_metadata(self):
        """Retourne les métadonnées du livre."""
        self.load()
        
        if not self.epub_book:
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
    
    def search(self, query):
        """Recherche un terme dans le livre et retourne les pages correspondantes."""
        self.load()
        
        query = query.lower()
        results = []
        
        for page_data in self.pages:
            if query in page_data['html'].lower():
                results.append({
                    'page': page_data['page_number'],
                    'preview': self._extract_preview(page_data['html'], query)
                })
        
        return results
    
    def _extract_preview(self, html, query, context_length=100):
        """Extrait un aperçu du texte autour du terme recherché."""
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        
        query_lower = query.lower()
        text_lower = text.lower()
        
        index = text_lower.find(query_lower)
        if index == -1:
            return text[:context_length] + "..."
        
        start = max(0, index - context_length)
        end = min(len(text), index + len(query) + context_length)
        
        preview = text[start:end]
        if start > 0:
            preview = "..." + preview
        if end < len(text):
            preview = preview + "..."
        
        return preview
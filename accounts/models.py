# accounts/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UserProfile(models.Model):
    """Profil utilisateur avec solde et abonnement."""
    
    PLAN_CHOICES = [
        ('free', 'Gratuit'),
        ('basic', 'Basic (500 FCFA/mois)'),
        ('premium', 'Premium (1000 FCFA/mois)'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Solde
    balance = models.PositiveIntegerField(default=0, verbose_name="Solde (FCFA)")
    
    # Abonnement
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free', verbose_name="Forfait")
    plan_expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Expiration du forfait")
    
    # 🆕 Livres achetés individuellement
    purchased_books = models.ManyToManyField(
        'books.Book', 
        blank=True,
        related_name='purchasers',
        verbose_name="Livres achetés"
    )
    
    # Statistiques
    total_spent = models.PositiveIntegerField(default=0, verbose_name="Total dépensé (FCFA)")
    books_read = models.PositiveIntegerField(default=0, verbose_name="Livres lus")
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.get_plan_display()} - {self.balance} FCFA"
    
    def has_active_plan(self):
        """Vérifie si l'utilisateur a un abonnement actif."""
        if self.plan == 'free':
            return True  # Gratuit toujours actif
        return self.plan_expires_at and self.plan_expires_at > timezone.now()
    
    def can_read_full_book(self):
        """Vérifie si l'utilisateur peut lire un livre en entier."""
        if self.plan == 'premium':
            return True
        if self.plan == 'basic':
            return True
        # Free : lecture limitée
        return False
    
    def can_download(self):
        """Vérifie si l'utilisateur peut télécharger."""
        return self.plan == 'premium'
    
    def get_reading_limit_pages(self):
        """Retourne le nombre de pages lisibles selon le forfait."""
        if self.plan == 'premium':
            return None  # Illimité
        if self.plan == 'basic':
            return None  # Illimité en ligne
        return 3  # Free : 3 pages d'aperçu
    
    def has_purchased(self, book):
        """Vérifie si l'utilisateur a acheté ce livre."""
        return self.purchased_books.filter(id=book.id).exists()
    
    def can_access_book(self, book):
        """Vérifie si l'utilisateur peut accéder à un livre."""
        # Premium : accès à tout
        if self.plan == 'premium':
            return True
        
        # Basic : accès en ligne à tout
        if self.plan == 'basic':
            return True
        
        # Achat unitaire : accès complet à ce livre
        if self.has_purchased(book):
            return True
        
        # Gratuit : lecture limitée
        return False
    
    def can_download_book(self, book):
        """Vérifie si l'utilisateur peut télécharger un livre."""
        # Premium : peut tout télécharger
        if self.plan == 'premium':
            return True
        
        # Achat unitaire : peut télécharger ce livre
        if self.has_purchased(book):
            return True
        
        return False
    
    def buy_book(self, book, price=100):
        """Achète un livre à l'unité."""
        if self.balance < price:
            return False, "Solde insuffisant"
        
        if self.has_purchased(book):
            return False, "Livre déjà acheté"
        
        self.balance -= price
        self.purchased_books.add(book)
        self.save()
        
        # Créer la transaction
        Transaction.objects.create(
            user=self.user,
            profile=self,
            type='purchase',
            amount=price,
            status='completed',
            description=f"Achat du livre : {book.title}"
        )
        
        return True, "Livre acheté avec succès !"
    
    def deduct_monthly(self):
        """Débite le compte pour le renouvellement mensuel."""
        prices = {'basic': 500, 'premium': 1000}
        price = prices.get(self.plan, 0)
        
        if price == 0:
            return True
        
        if self.balance >= price:
            self.balance -= price
            self.plan_expires_at = timezone.now() + timezone.timedelta(days=30)
            self.save()
            return True
        
        return False

class Transaction(models.Model):
    """Historique des transactions."""
    
    TYPE_CHOICES = [
        ('deposit', 'Recharge'),
        ('subscription', 'Abonnement'),
        ('purchase', 'Achat unitaire'),  # 🆕
        ('refund', 'Remboursement'),
        ('bonus', 'Bonus'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('completed', 'Complété'),
        ('failed', 'Échoué'),
        ('cancelled', 'Annulé'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='transactions', null=True)
    
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Type")
    amount = models.PositiveIntegerField(verbose_name="Montant (FCFA)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Statut")
    
    # Détails du paiement
    payment_method = models.CharField(max_length=50, blank=True, null=True, verbose_name="Méthode de paiement")
    reference = models.CharField(max_length=100, blank=True, null=True, verbose_name="Référence")
    
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.get_type_display()} - {self.amount} FCFA"
    
    def mark_completed(self):
        """Marque la transaction comme complétée et met à jour le solde."""
        self.status = 'completed'
        self.save()
        
        if self.type == 'deposit':
            self.user.profile.balance += self.amount
            self.user.profile.total_spent += self.amount
            self.user.profile.save()
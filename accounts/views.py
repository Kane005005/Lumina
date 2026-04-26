# accounts/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from .models import UserProfile, Transaction
from .serializers import (
    UserProfileSerializer, 
    TransactionSerializer,
    RechargeSerializer,
    SubscriptionSerializer,
    BuyBookSerializer,
    CheckAccessSerializer
)
from django.utils import timezone

class UserProfileViewSet(viewsets.ModelViewSet):
    """Gestion du profil utilisateur."""
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Retourne le profil de l'utilisateur connecté."""
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(profile)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def recharge(self, request):
        """Recharge le compte via Orange Money, Moov Money, Wave."""
        serializer = RechargeSerializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data['amount']
            payment_method = serializer.validated_data['payment_method']
            
            # Créer une transaction en attente
            transaction = Transaction.objects.create(
                user=request.user,
                type='deposit',
                amount=amount,
                status='pending',
                payment_method=payment_method,
                description=f"Recharge {amount} FCFA via {payment_method}"
            )
            
            # Simuler le paiement (à remplacer par vraie API)
            # Pour l'instant, on valide automatiquement
            transaction.mark_completed()
            
            return Response({
                'success': True,
                'message': f'Compte rechargé de {amount} FCFA',
                'new_balance': request.user.profile.balance,
                'transaction_id': transaction.id
            })
        
        return Response(serializer.errors, status=400)
    
    @action(detail=False, methods=['post'])
    def subscribe(self, request):
        """Souscrire à un forfait."""
        serializer = SubscriptionSerializer(data=request.data)
        if serializer.is_valid():
            plan = serializer.validated_data['plan']
            profile = request.user.profile
            
            prices = {
                'basic': 500,
                'premium': 1000,
                'annual_basic': 4500,   # 500*12 - 25%
                'annual_premium': 9000, # 1000*12 - 25%
            }
            
            price = prices.get(plan, 0)
            
            if profile.balance < price:
                return Response({
                    'success': False,
                    'message': f'Solde insuffisant. Vous avez {profile.balance} FCFA, il faut {price} FCFA.',
                    'current_balance': profile.balance,
                    'required': price
                }, status=400)
            
            # Débiter le compte
            profile.balance -= price
            
            # Définir le plan
            if plan.startswith('annual'):
                profile.plan = plan.replace('annual_', '')
                profile.plan_expires_at = timezone.now() + timezone.timedelta(days=365)
            else:
                profile.plan = plan
                profile.plan_expires_at = timezone.now() + timezone.timedelta(days=30)
            
            profile.save()
            
            # Créer la transaction
            Transaction.objects.create(
                user=request.user,
                type='subscription',
                amount=price,
                status='completed',
                description=f"Abonnement {profile.get_plan_display()}"
            )
            
            return Response({
                'success': True,
                'message': f'Abonnement {profile.get_plan_display()} activé !',
                'plan': profile.plan,
                'expires_at': profile.plan_expires_at,
                'new_balance': profile.balance
            })
        
        return Response(serializer.errors, status=400)
    
    @action(detail=False, methods=['get'])
    def transactions(self, request):
        """Historique des transactions."""
        transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:50]
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data)
    
    # 🆕 Nouvelles actions pour l'achat de livres
    @action(detail=False, methods=['post'])
    def buy_book(self, request):
        """Acheter un livre à l'unité (100 FCFA)."""
        serializer = BuyBookSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        book_id = serializer.validated_data['book_id']
        
        try:
            from books.models import Book
            book = Book.objects.get(id=book_id, is_active=True)
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Livre introuvable'
            }, status=404)
        
        profile = request.user.profile
        
        # Vérifier si déjà acheté
        if profile.has_purchased(book):
            return Response({
                'success': True,
                'message': 'Vous possédez déjà ce livre',
                'already_purchased': True
            })
        
        # Vérifier si premium (déjà accès)
        if profile.plan == 'premium':
            return Response({
                'success': True,
                'message': 'Vous avez déjà accès à ce livre avec votre abonnement Premium',
                'already_premium': True
            })
        
        # Acheter le livre
        success, message = profile.buy_book(book, price=100)
        
        if success:
            return Response({
                'success': True,
                'message': message,
                'new_balance': profile.balance,
                'book': {
                    'id': book.id,
                    'title': book.title,
                }
            })
        
        return Response({
            'success': False,
            'message': message,
            'current_balance': profile.balance,
            'required': 100
        }, status=400)
    
    @action(detail=False, methods=['get'])
    def my_books(self, request):
        """Liste des livres achetés par l'utilisateur."""
        profile = request.user.profile
        books = profile.purchased_books.filter(is_active=True)
        
        try:
            from books.serializers import BookSerializer
            serializer = BookSerializer(books, many=True, context={'request': request})
            return Response(serializer.data)
        except ImportError:
            # Fallback si le serializer BookSerializer n'existe pas
            return Response([{
                'id': book.id,
                'title': book.title,
            } for book in books])
    
    @action(detail=False, methods=['get'])
    def check_access(self, request):
        """Vérifie l'accès à un livre spécifique."""
        serializer = CheckAccessSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response({'error': 'book_id requis'}, status=400)
        
        book_id = serializer.validated_data['book_id']
        
        try:
            from books.models import Book
            book = Book.objects.get(id=book_id, is_active=True)
        except Exception as e:
            return Response({'error': 'Livre introuvable'}, status=404)
        
        profile = request.user.profile
        
        return Response({
            'book_id': book.id,
            'can_read': profile.can_access_book(book),
            'can_download': profile.can_download_book(book),
            'reading_limit': profile.get_reading_limit_pages(),
            'is_purchased': profile.has_purchased(book),
            'is_premium': profile.plan == 'premium',
            'plan': profile.plan
        })

class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """Historique des transactions (lecture seule)."""
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by('-created_at')
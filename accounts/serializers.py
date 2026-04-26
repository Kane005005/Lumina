# accounts/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, Transaction
from django.utils import timezone

class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'username', 'email',
            'balance', 'plan', 'plan_expires_at',
            'days_remaining', 'total_spent', 'books_read',
            'purchased_books', 'created_at'
        ]
        read_only_fields = ['balance', 'total_spent', 'books_read', 'purchased_books']
    
    def get_days_remaining(self, obj):
        if obj.plan_expires_at:
            delta = obj.plan_expires_at - timezone.now()
            return max(0, delta.days)
        return None

class TransactionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

class RechargeSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=100, max_value=100000)
    payment_method = serializers.ChoiceField(
        choices=['orange_money', 'moov_money', 'wave']
    )
    phone_number = serializers.CharField(required=False)

class SubscriptionSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(
        choices=['basic', 'premium', 'annual_basic', 'annual_premium']
    )

# 🆕 Nouveaux serializers pour l'achat de livres
class BuyBookSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(required=True)

class CheckAccessSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(required=True)
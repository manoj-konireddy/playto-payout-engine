from rest_framework import serializers

from .models import LedgerEntry, Payout


class PayoutCreateSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.IntegerField(min_value=1)


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = [
            'id',
            'amount_paise',
            'status',
            'attempt_count',
            'failure_reason',
            'created_at',
            'updated_at',
        ]


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ['id', 'entry_type', 'amount_paise', 'description', 'created_at']

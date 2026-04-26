from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Merchant(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    available_balance_paise = models.BigIntegerField(default=0)
    held_balance_paise = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_balance_paise(self):
        return self.available_balance_paise + self.held_balance_paise

    def __str__(self):
        return self.name


class BankAccount(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='bank_accounts')
    account_holder_name = models.CharField(max_length=120)
    account_number = models.CharField(max_length=40)
    ifsc_code = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.account_holder_name} ({self.account_number[-4:]})'


class LedgerEntry(models.Model):
    CREDIT = 'credit'
    DEBIT = 'debit'
    ENTRY_TYPE_CHOICES = [
        (CREDIT, 'Credit'),
        (DEBIT, 'Debit'),
    ]

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='ledger_entries')
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)
    amount_paise = models.BigIntegerField()
    description = models.CharField(max_length=255)
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']


class Payout(models.Model):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (PROCESSING, 'Processing'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
    ]
    LEGAL_TRANSITIONS = {
        PENDING: {PROCESSING},
        PROCESSING: {COMPLETED, FAILED},
        COMPLETED: set(),
        FAILED: set(),
    }

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='payouts')
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT)
    amount_paise = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    idempotency_key = models.UUIDField()
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['merchant', 'idempotency_key'],
                name='unique_payout_per_merchant_idempotency',
            )
        ]
        ordering = ['-created_at', '-id']

    def transition_to(self, next_status):
        if next_status not in self.LEGAL_TRANSITIONS[self.status]:
            raise ValidationError(f'Illegal transition from {self.status} to {next_status}')
        self.status = next_status


class IdempotencyRecord(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='idempotency_records')
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    response_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['merchant', 'key'], name='unique_merchant_idempotency_key')
        ]

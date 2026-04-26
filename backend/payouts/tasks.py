import random
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import LedgerEntry, Merchant, Payout
from .services import stale_processing_payouts


@shared_task
def process_payouts():
    for payout in stale_processing_payouts():
        _process_single_payout(payout.id)


def _process_single_payout(payout_id):
    with transaction.atomic():
        payout = Payout.objects.select_for_update().select_related('merchant').get(id=payout_id)
        if payout.status == Payout.PENDING:
            payout.transition_to(Payout.PROCESSING)
            payout.attempt_count += 1
            payout.save(update_fields=['status', 'attempt_count', 'updated_at'])
        elif payout.status == Payout.PROCESSING:
            if payout.attempt_count >= 3:
                _fail_and_refund(payout, 'Max retry attempts exceeded')
                return
            payout.attempt_count += 1
            payout.save(update_fields=['attempt_count', 'updated_at'])
        else:
            return

        outcome = random.random()
        if outcome < 0.7:
            payout.transition_to(Payout.COMPLETED)
            payout.save(update_fields=['status', 'updated_at'])
            Merchant.objects.filter(id=payout.merchant_id).update(
                held_balance_paise=F('held_balance_paise') - payout.amount_paise
            )
        elif outcome < 0.9:
            _fail_and_refund(payout, 'Bank settlement failed')
        else:
            backoff_seconds = 2 ** payout.attempt_count
            payout.next_attempt_at = timezone.now() + timedelta(seconds=backoff_seconds)
            payout.save(update_fields=['next_attempt_at', 'updated_at'])


def _fail_and_refund(payout, reason):
    payout.transition_to(Payout.FAILED)
    payout.failure_reason = reason
    payout.save(update_fields=['status', 'failure_reason', 'updated_at'])
    Merchant.objects.filter(id=payout.merchant_id).update(
        held_balance_paise=F('held_balance_paise') - payout.amount_paise,
        available_balance_paise=F('available_balance_paise') + payout.amount_paise,
    )
    LedgerEntry.objects.create(
        merchant_id=payout.merchant_id,
        entry_type=LedgerEntry.CREDIT,
        amount_paise=payout.amount_paise,
        description=f'Refund for failed payout #{payout.id}',
        reference_type='payout_refund',
        reference_id=str(payout.id),
    )

import hashlib
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.utils import timezone
from rest_framework import status

from .models import BankAccount, IdempotencyRecord, LedgerEntry, Merchant, Payout


class DuplicateIdempotencyInFlight(Exception):
    pass


class IdempotencyConflict(Exception):
    pass


def _payload_hash(payload):
    canonical = f"{payload['amount_paise']}:{payload['bank_account_id']}"
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def create_payout_with_idempotency(*, merchant_id, idempotency_key, payload):
    now = timezone.now()
    payload_digest = _payload_hash(payload)
    expires_at = now + timedelta(hours=24)

    with transaction.atomic():
        merchant = Merchant.objects.select_for_update().get(id=merchant_id)

        try:
            with transaction.atomic():
                record = IdempotencyRecord.objects.create(
                    merchant=merchant,
                    key=idempotency_key,
                    request_hash=payload_digest,
                    expires_at=expires_at,
                )
        except IntegrityError:
            record = IdempotencyRecord.objects.select_for_update().get(
                merchant=merchant,
                key=idempotency_key,
            )
            if record.expires_at <= now:
                raise IdempotencyConflict('Idempotency key expired')
            if record.request_hash != payload_digest:
                raise IdempotencyConflict('Idempotency key reused with different payload')
            if record.response_body is None:
                raise DuplicateIdempotencyInFlight('Original request is still being processed')
            return record.response_status_code, record.response_body

        bank_account = BankAccount.objects.get(
            id=payload['bank_account_id'],
            merchant=merchant,
            is_active=True,
        )
        amount = payload['amount_paise']
        updated = Merchant.objects.filter(
            id=merchant.id,
            available_balance_paise__gte=amount,
        ).update(
            available_balance_paise=F('available_balance_paise') - amount,
            held_balance_paise=F('held_balance_paise') + amount,
        )
        if updated == 0:
            response = {'error': 'Insufficient available balance'}
            record.response_status_code = status.HTTP_400_BAD_REQUEST
            record.response_body = response
            record.save(update_fields=['response_status_code', 'response_body', 'updated_at'])
            return status.HTTP_400_BAD_REQUEST, response

        payout = Payout.objects.create(
            merchant=merchant,
            bank_account=bank_account,
            amount_paise=amount,
            idempotency_key=idempotency_key,
            status=Payout.PENDING,
        )
        LedgerEntry.objects.create(
            merchant=merchant,
            entry_type=LedgerEntry.DEBIT,
            amount_paise=amount,
            description=f'Funds held for payout #{payout.id}',
            reference_type='payout',
            reference_id=str(payout.id),
        )
        response = {
            'id': payout.id,
            'amount_paise': payout.amount_paise,
            'status': payout.status,
            'attempt_count': payout.attempt_count,
            'created_at': payout.created_at.isoformat(),
        }
        record.response_status_code = status.HTTP_201_CREATED
        record.response_body = response
        record.save(update_fields=['response_status_code', 'response_body', 'updated_at'])
        from .tasks import process_payouts

        transaction.on_commit(lambda: process_payouts.delay())
        return status.HTTP_201_CREATED, response


def get_dashboard_data(merchant):
    ledger = merchant.ledger_entries.all()[:10]
    payouts = merchant.payouts.all()[:20]
    credits = merchant.ledger_entries.filter(entry_type=LedgerEntry.CREDIT).aggregate(
        total=Sum('amount_paise')
    )['total'] or 0
    debits = merchant.ledger_entries.filter(entry_type=LedgerEntry.DEBIT).aggregate(
        total=Sum('amount_paise')
    )['total'] or 0
    return {
        'merchant': {'id': merchant.id, 'name': merchant.name},
        'available_balance_paise': merchant.available_balance_paise,
        'held_balance_paise': merchant.held_balance_paise,
        'ledger_invariant': {
            'credits_paise': credits,
            'debits_paise': debits,
            'computed_available_paise': credits - debits,
        },
        'recent_ledger': [
            {
                'id': e.id,
                'entry_type': e.entry_type,
                'amount_paise': e.amount_paise,
                'description': e.description,
                'created_at': e.created_at.isoformat(),
            }
            for e in ledger
        ],
        'payouts': [
            {
                'id': p.id,
                'amount_paise': p.amount_paise,
                'status': p.status,
                'attempt_count': p.attempt_count,
                'failure_reason': p.failure_reason,
                'created_at': p.created_at.isoformat(),
                'updated_at': p.updated_at.isoformat(),
            }
            for p in payouts
        ],
        'bank_accounts': [
            {
                'id': b.id,
                'label': f'{b.account_holder_name} - {b.account_number[-4:]} ({b.ifsc_code})',
            }
            for b in merchant.bank_accounts.filter(is_active=True).order_by('id')
        ],
    }


def stale_processing_payouts():
    cutoff = timezone.now() - timedelta(seconds=30)
    return Payout.objects.filter(
        Q(status=Payout.PENDING)
        | Q(status=Payout.PROCESSING, updated_at__lt=cutoff, next_attempt_at__lte=timezone.now())
    ).select_related('merchant')

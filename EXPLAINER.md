# EXPLAINER

## 1) The Ledger

Balance calculation query used by the dashboard:

```python
credits = merchant.ledger_entries.filter(entry_type=LedgerEntry.CREDIT).aggregate(
    total=Sum('amount_paise')
)['total'] or 0
debits = merchant.ledger_entries.filter(entry_type=LedgerEntry.DEBIT).aggregate(
    total=Sum('amount_paise')
)['total'] or 0
computed_available = credits - debits
```

Why this model:

- Every money movement is an append-only ledger row in paise integer units.
- Holding funds at payout request time is recorded as a debit, and payout failure creates a compensating credit.
- This keeps the available balance auditable as `credits - debits` and avoids floating point errors.

## 2) The Lock

Code that prevents concurrent overdraft:

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    updated = Merchant.objects.filter(
        id=merchant.id,
        available_balance_paise__gte=amount,
    ).update(
        available_balance_paise=F('available_balance_paise') - amount,
        held_balance_paise=F('held_balance_paise') + amount,
    )
```

Primitive used:

- `SELECT ... FOR UPDATE` row lock on merchant inside a DB transaction.
- Atomic `UPDATE ... WHERE available_balance_paise >= amount` prevents check-then-deduct races.

## 3) The Idempotency

How key dedupe works:

- `IdempotencyRecord` has a unique constraint on `(merchant, key)`.
- On first request, record is created with request hash and later filled with response body + status.
- Duplicate request with same key and same payload returns the previously stored response exactly.
- Duplicate request with same key but different payload returns conflict.
- Keys expire after 24h via `expires_at`.

In-flight duplicate behavior:

- If duplicate arrives before first request has stored response body, API returns `409` with `Original request is still being processed`.

## 4) The State Machine

Where illegal transitions are blocked:

```python
LEGAL_TRANSITIONS = {
    PENDING: {PROCESSING},
    PROCESSING: {COMPLETED, FAILED},
    COMPLETED: set(),
    FAILED: set(),
}

def transition_to(self, next_status):
    if next_status not in self.LEGAL_TRANSITIONS[self.status]:
        raise ValidationError(f'Illegal transition from {self.status} to {next_status}')
    self.status = next_status
```

This blocks failed-to-completed and all backward jumps.

## 5) The AI Audit

Subtly wrong AI-generated pattern:

```python
merchant = Merchant.objects.get(id=merchant_id)
if merchant.available_balance_paise < amount:
    return error
merchant.available_balance_paise -= amount
merchant.held_balance_paise += amount
merchant.save()
```

Why it is wrong:

- It does check-then-write in Python without DB row lock.
- Two concurrent requests can both pass the balance check and overdraw.

What I replaced it with:

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    updated = Merchant.objects.filter(
        id=merchant.id,
        available_balance_paise__gte=amount,
    ).update(
        available_balance_paise=F('available_balance_paise') - amount,
        held_balance_paise=F('held_balance_paise') + amount,
    )
```

- This makes overdraft impossible under concurrent requests at DB level.

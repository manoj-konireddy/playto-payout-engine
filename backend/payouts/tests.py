import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from .models import BankAccount, LedgerEntry, Merchant, Payout


class PayoutEngineTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.merchant = Merchant.objects.create(
            name='Concurrency Merchant',
            email='concurrency@test.dev',
            available_balance_paise=10000,
            held_balance_paise=0,
        )
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_holder_name='Concurrency Merchant',
            account_number='12345678901',
            ifsc_code='HDFC0001234',
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type=LedgerEntry.CREDIT,
            amount_paise=10000,
            description='Seed credit',
        )

    def _post_payout(self, idem_key):
        client = APIClient()
        return client.post(
            '/api/v1/payouts',
            {'amount_paise': 6000, 'bank_account_id': self.bank_account.id},
            format='json',
            HTTP_X_MERCHANT_ID=str(self.merchant.id),
            HTTP_IDEMPOTENCY_KEY=idem_key,
        )

    def test_concurrent_payout_requests_only_one_succeeds(self):
        barrier = threading.Barrier(2)

        def task(key):
            barrier.wait()
            return self._post_payout(key).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(task, [str(uuid.uuid4()), str(uuid.uuid4())]))

        self.assertEqual(results.count(201), 1)
        self.assertEqual(results.count(400), 1)
        self.merchant.refresh_from_db()
        self.assertEqual(self.merchant.available_balance_paise, 4000)
        self.assertEqual(self.merchant.held_balance_paise, 6000)
        self.assertEqual(Payout.objects.count(), 1)

    def test_idempotency_returns_exact_same_response(self):
        idem_key = str(uuid.uuid4())
        first = self._post_payout(idem_key)
        second = self._post_payout(idem_key)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertJSONEqual(first.content.decode('utf-8'), second.content.decode('utf-8'))
        self.assertEqual(Payout.objects.count(), 1)

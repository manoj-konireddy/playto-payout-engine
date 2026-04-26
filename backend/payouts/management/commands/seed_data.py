import random

from django.core.management.base import BaseCommand
from django.db import transaction

from payouts.models import BankAccount, LedgerEntry, Merchant


class Command(BaseCommand):
    help = 'Seed merchants, bank accounts, and credit ledger entries.'

    @transaction.atomic
    def handle(self, *args, **options):
        if Merchant.objects.exists():
            self.stdout.write(self.style.WARNING('Seed already exists, skipping.'))
            return

        merchants = []
        for i in range(1, 4):
            merchants.append(
                Merchant.objects.create(
                    name=f'Merchant {i}',
                    email=f'merchant{i}@playto.dev',
                )
            )

        for merchant in merchants:
            BankAccount.objects.create(
                merchant=merchant,
                account_holder_name=merchant.name,
                account_number=f'00000012345{merchant.id}',
                ifsc_code='HDFC0001234',
            )

            total_credit = 0
            for _ in range(5):
                amount = random.choice([15000, 25000, 50000, 100000])
                total_credit += amount
                LedgerEntry.objects.create(
                    merchant=merchant,
                    entry_type=LedgerEntry.CREDIT,
                    amount_paise=amount,
                    description='Simulated customer payment',
                    reference_type='payment',
                )
            merchant.available_balance_paise = total_credit
            merchant.save(update_fields=['available_balance_paise'])

        self.stdout.write(self.style.SUCCESS('Seeded 3 merchants with ledger credits.'))

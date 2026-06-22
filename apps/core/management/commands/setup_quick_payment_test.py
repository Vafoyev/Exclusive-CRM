"""
Setup test data for quick payment functionality
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from apps.users.models import User
from apps.organizations.models import Organization, Branch
from apps.finance.models import Account


class Command(BaseCommand):
    help = 'Setup test data for quick payment functionality'

    def handle(self, *args, **kwargs):
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS('SETTING UP QUICK PAYMENT TEST DATA'))
        self.stdout.write("=" * 60)

        # Create Organization
        self.stdout.write("\n1. Creating Organization...")
        org, created = Organization.objects.get_or_create(
            name="Quick Payment Test Center",
            defaults={
                'subdomain': 'quickpay-test',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f"   ✅ Organization created: {org.name}")
        else:
            self.stdout.write(f"   ℹ️  Organization exists: {org.name}")

        # Create Branch
        self.stdout.write("\n2. Creating Branch...")
        branch, created = Branch.objects.get_or_create(
            organization=org,
            name="Test Branch",
            defaults={
                'is_main': True,
            }
        )
        if created:
            self.stdout.write(f"   ✅ Branch created: {branch.name}")

        # Create Test Accounts
        self.stdout.write("\n3. Creating Test Accounts...")
        account_data = [
            ('Main Cash Register', 'cash', Decimal('5000000')),
            ('Bank Account', 'bank', Decimal('10000000')),
            ('Card Terminal', 'card', Decimal('2000000')),
        ]
        
        for acc_name, acc_type, balance in account_data:
            account, created = Account.objects.get_or_create(
                organization=org,
                name=acc_name,
                defaults={
                    'balance': balance,
                    'account_type': acc_type,
                }
            )
            if created:
                self.stdout.write(f"   ✅ Account created: {account.name} ({account.account_type}) - {account.balance:,} UZS")
            else:
                self.stdout.write(f"   ℹ️  Account exists: {account.name}")

        # Create Test Student
        self.stdout.write("\n4. Creating Test Student...")
        student, created = User.objects.get_or_create(
            phone='+998990000001',
            defaults={
                'first_name': 'QuickPay',
                'last_name': 'TestStudent',
                'role': 'student',
                'organization': org,
                'branch': branch,
                'is_active': True,
            }
        )
        if created:
            student.set_password('test123')
            student.save()
            self.stdout.write(f"   ✅ Student created: {student.full_name}")
        else:
            self.stdout.write(f"   ℹ️  Student exists: {student.full_name}")

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS('SETUP COMPLETE'))
        self.stdout.write("=" * 60)
        self.stdout.write(f"""
📊 TEST DATA SUMMARY:
   • Organization: {org.name}
   • Branch: {branch.name}
   • Accounts: {Account.objects.filter(organization=org, is_deleted=False).count()}
   • Student: {student.full_name} (+998990000001 / test123)

📱 LOGIN CREDENTIALS:
   Super Admin: Use existing super admin credentials
   Test Student: +998990000001 / test123

💡 USAGE:
   1. Login as super admin
   2. Go to super admin dashboard
   3. Click "To'lov" button
   4. Search for "QuickPay TestStudent" 
   5. Select a payment method and account
   6. Enter amount and submit
        """)
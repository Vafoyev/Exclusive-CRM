from django import forms
from .models import Account, Transaction, TransactionCategory

INPUT_CLASSES = "w-full px-4 py-2 rounded-lg bg-gray-50 border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:bg-white"

class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['name', 'account_type', 'balance']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Masalan: Asosiy kassa'}),
            'account_type': forms.Select(attrs={'class': INPUT_CLASSES}),
            'balance': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'placeholder': '0'}),
        }

class CategoryForm(forms.ModelForm):
    """Kirim va chiqim kategoriyalari uchun form"""
    class Meta:
        model = TransactionCategory
        fields = ['name', 'transaction_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Masalan: Kurs to\'lovi'}),
            'transaction_type': forms.Select(attrs={'class': INPUT_CLASSES}),
        }

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['account', 'category', 'amount', 'description']
        widgets = {
            'account': forms.Select(attrs={'class': INPUT_CLASSES}),
            'category': forms.Select(attrs={'class': INPUT_CLASSES}),
            'amount': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Summa', 'min': '0'}),
            'description': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 3, 'placeholder': 'Izoh...'}),
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        transaction_type = kwargs.pop('transaction_type', None)
        super().__init__(*args, **kwargs)

        if organization:
            self.fields['account'].queryset = Account.objects.filter(
                organization=organization, is_deleted=False
            )

            if transaction_type:
                self.fields['category'].queryset = TransactionCategory.objects.filter(
                    organization=organization,
                    transaction_type=transaction_type,
                    is_deleted=False
                )

            # Agar kategoriya bo'lmasa, bo'sh ko'rsatmaslik uchun
            if not self.fields['category'].queryset.exists():
                self.fields['category'].help_text = "Diqqat: Hozircha kategoriya yo'q. Avval kategoriya qo'shing."

class StudentPaymentForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['account', 'category', 'amount', 'payment_method', 'description', 'receipt_image', 'receipt_file']
        widgets = {
            'account': forms.Select(attrs={'class': INPUT_CLASSES}),
            'category': forms.Select(attrs={'class': INPUT_CLASSES}),
            'amount': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'placeholder': "To'lov summasi", 'min': '0'}),
            'payment_method': forms.Select(attrs={'class': INPUT_CLASSES, 'onchange': 'toggleReceiptFields(this)'}),
            'description': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 2, 'placeholder': 'Izoh...'}),
            'receipt_image': forms.FileInput(attrs={'class': INPUT_CLASSES, 'accept': 'image/*'}),
            'receipt_file': forms.FileInput(attrs={'class': INPUT_CLASSES, 'accept': '.pdf'}),
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if organization:
            self.fields['account'].queryset = Account.objects.filter(organization=organization, is_deleted=False)
            self.fields['category'].queryset = TransactionCategory.objects.filter(organization=organization, transaction_type='income', is_deleted=False)

        self.fields['receipt_image'].required = False
        self.fields['receipt_file'].required = False
        self.fields['description'].required = False


class AdminCashTransactionForm(forms.ModelForm):
    """Admin kassa kirim-chiqim formasi (kategoriya, summa, to'lov usuli, izoh)."""
    class Meta:
        model = Transaction
        fields = ['category', 'amount', 'payment_method', 'description']
        widgets = {
            'category': forms.Select(attrs={'class': INPUT_CLASSES}),
            'amount': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Summa', 'min': '0'}),
            'payment_method': forms.Select(attrs={'class': INPUT_CLASSES}),
            'description': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 3, 'placeholder': 'Izoh...'}),
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        transaction_type = kwargs.pop('transaction_type', None)
        super().__init__(*args, **kwargs)
        self.fields['payment_method'].required = False

        if organization and transaction_type:
            self.fields['category'].queryset = TransactionCategory.objects.filter(
                organization=organization,
                transaction_type=transaction_type,
                is_deleted=False
            )

        if not self.fields['category'].queryset.exists():
            self.fields['category'].help_text = "Diqqat: Hozircha kategoriya yo'q. Avval kategoriya qo'shing."

    def clean_payment_method(self):
        return self.cleaned_data.get('payment_method') or 'cash'

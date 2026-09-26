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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['balance'].required = False
        if not self.instance.pk:
            self.fields['balance'].initial = 0

    def clean_balance(self):
        val = self.cleaned_data.get('balance')
        return val if val is not None else 0

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
            from .services import ensure_default_finance_data
            ensure_default_finance_data(organization)

        self.fields['category'].required = False
        self.fields['category'].empty_label = "- Tanlang (ixtiyoriy) -"
        self.fields['description'].required = False

        acc_qs = Account.objects.filter(is_deleted=False)
        if organization:
            acc_qs = acc_qs.filter(organization=organization)
        self.fields['account'].queryset = acc_qs

        cat_qs = TransactionCategory.objects.filter(is_deleted=False)
        if organization:
            cat_qs = cat_qs.filter(organization=organization)
        if transaction_type:
            cat_qs = cat_qs.filter(transaction_type=transaction_type)
        self.fields['category'].queryset = cat_qs

        if not self.fields['category'].queryset.exists():
            self.fields['category'].help_text = "Hozircha kategoriya yo'q (ixtiyoriy)."

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
            from .services import ensure_default_finance_data
            ensure_default_finance_data(organization)

        # 1. Kassalar
        acc_qs = Account.objects.filter(is_deleted=False)
        if organization:
            acc_qs = acc_qs.filter(organization=organization)
        if not acc_qs.exists() and organization:
            Account.objects.create(organization=organization, name="Asosiy Kassa (Naqd)", account_type='cash', balance=0)
            acc_qs = Account.objects.filter(organization=organization, is_deleted=False)

        self.fields['account'].queryset = acc_qs
        if acc_qs.exists():
            first_acc = acc_qs.first()
            self.fields['account'].initial = first_acc.pk

        # 2. To'lov turi (Kategoriya)
        cat_qs = TransactionCategory.objects.filter(is_deleted=False, transaction_type='income')
        if organization:
            cat_qs = cat_qs.filter(organization=organization)
        if not cat_qs.exists() and organization:
            TransactionCategory.objects.create(organization=organization, name="Kurs to'lovi", transaction_type='income')
            cat_qs = TransactionCategory.objects.filter(organization=organization, is_deleted=False, transaction_type='income')

        self.fields['category'].queryset = cat_qs
        self.fields['category'].required = False
        self.fields['category'].empty_label = "- To'lov turi (ixtiyoriy) -"
        if cat_qs.exists():
            self.fields['category'].initial = cat_qs.first().pk

        self.fields['receipt_image'].required = False
        self.fields['receipt_file'].required = False
        self.fields['description'].required = False
        self.fields['payment_method'].initial = 'cash'

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if not amount or amount <= 0:
            raise forms.ValidationError("Summa 0 dan katta bo'lishi kerak!")
        return amount


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
        self.fields['category'].required = False
        self.fields['category'].empty_label = "- Kategoriya tanlang (ixtiyoriy) -"
        self.fields['payment_method'].required = False
        self.fields['payment_method'].initial = 'cash'
        self.fields['description'].required = False

        if organization and transaction_type:
            self.fields['category'].queryset = TransactionCategory.objects.filter(
                organization=organization,
                transaction_type=transaction_type,
                is_deleted=False
            )
        elif transaction_type:
            self.fields['category'].queryset = TransactionCategory.objects.filter(
                transaction_type=transaction_type,
                is_deleted=False
            )

        if not self.fields['category'].queryset.exists():
            self.fields['category'].help_text = "Hozircha kategoriya yaratilmagan (ixtiyoriy)."

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if not amount or amount <= 0:
            raise forms.ValidationError("Summa 0 dan katta bo'lishi kerak!")
        return amount

    def clean_payment_method(self):
        return self.cleaned_data.get('payment_method') or 'cash'

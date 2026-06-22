from django.contrib import admin
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from .models import Account, TransactionCategory, Transaction, CashSubmission
from .services import confirm_transaction
from django.contrib import messages


@admin.register(Account)
class AccountAdmin(ModelAdmin):
    list_display = ('name', 'account_type', 'formatted_balance', 'organization')
    list_filter_submit = True

    @admin.display(description="Balans")
    def formatted_balance(self, obj):
        formatted = "{:,.0f}".format(obj.balance)
        color = "#10b981" if obj.balance >= 0 else "#ef4444"
        return mark_safe(
            f'<span style="color: {color}; font-weight: bold;">{formatted} so\'m</span>'
        )


@admin.register(TransactionCategory)
class CategoryAdmin(ModelAdmin):
    list_display = ('name', 'transaction_type')
    list_filter_submit = True


@admin.register(Transaction)
class TransactionAdmin(ModelAdmin):
    list_display = ('amount_colored', 'transaction_type', 'account', 'student', 'status_colored', 'created_at')
    list_filter = ('status', 'transaction_type', 'account', 'category')
    search_fields = ('student__phone', 'student__first_name', 'description')
    readonly_fields = ('created_by', 'confirmed_by', 'confirmed_at')
    list_filter_submit = True

    actions = ['approve_transactions']

    @admin.display(description="Summa")
    def amount_colored(self, obj):
        color = '#10b981' if obj.transaction_type == 'income' else '#ef4444'
        sign = "+" if obj.transaction_type == 'income' else "-"
        formatted_amount = "{:,.0f}".format(obj.amount)
        return mark_safe(
            f'<span style="color: {color}; font-weight: bold;">{sign} {formatted_amount} so\'m</span>'
        )

    @admin.display(description="Status")
    def status_colored(self, obj):
        colors = {'pending': '#f59e0b', 'confirmed': '#10b981', 'rejected': '#ef4444'}
        bg_color = colors.get(obj.status, '#6b7280')
        status_text = obj.get_status_display()
        return mark_safe(
            f'<span style="background-color: {bg_color}; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">{status_text}</span>'
        )

    # Admin paneldan "Action" orqali tasdiqlash
    def approve_transactions(self, request, queryset):
        count = 0
        for tx in queryset:
            if tx.status == 'pending':
                try:
                    confirm_transaction(tx.id, request.user)
                    count += 1
                except Exception as e:
                    self.message_user(request, f"Xatolik (ID: {tx.id}): {e}", level=messages.ERROR)

        self.message_user(request, f"{count} ta tranzaksiya tasdiqlandi va balanslar yangilandi.")

    approve_transactions.short_description = "Tanlanganlarni tasdiqlash (Balansga o'tkazish)"

    # Avtomatik "Created By" ni qo'shish
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CashSubmission)
class CashSubmissionAdmin(ModelAdmin):
    list_display = ('admin_user', 'period_type', 'period_start', 'period_end', 'net_amount_colored', 'status_colored', 'created_at')
    list_filter = ('status', 'period_type')
    search_fields = ('admin_user__phone', 'admin_user__first_name', 'admin_user__last_name')
    readonly_fields = ('approved_by', 'approved_at')
    list_filter_submit = True

    @admin.display(description="Sof summa")
    def net_amount_colored(self, obj):
        formatted = "{:,.0f}".format(obj.net_amount)
        color = "#10b981" if obj.net_amount >= 0 else "#ef4444"
        return mark_safe(
            f'<span style="color: {color}; font-weight: bold;">{formatted} so\'m</span>'
        )

    @admin.display(description="Holat")
    def status_colored(self, obj):
        colors = {'pending': '#f59e0b', 'approved': '#10b981', 'rejected': '#ef4444'}
        bg_color = colors.get(obj.status, '#6b7280')
        status_text = obj.get_status_display()
        return mark_safe(
            f'<span style="background-color: {bg_color}; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px;">{status_text}</span>'
        )
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.core.audit import log_user_action
from .models import NotificationTemplate, NotificationLog
from .services import send_template_notification, create_system_notification
from django import forms


class NotificationTemplateForm(forms.ModelForm):
    class Meta:
        model = NotificationTemplate
        fields = ['title', 'code', 'message_type', 'body']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-4 py-2 rounded-lg border focus:ring-2 border-gray-300'}),
            'code': forms.TextInput(attrs={'class': 'w-full px-4 py-2 rounded-lg border focus:ring-2 border-gray-300'}),
            'message_type': forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-lg border focus:ring-2 border-gray-300'}),
            'body': forms.Textarea(attrs={'class': 'w-full px-4 py-2 rounded-lg border focus:ring-2 border-gray-300', 'rows': 5}),
        }


@login_required
def template_list(request):
    templates = NotificationTemplate.objects.filter(is_deleted=False)
    if request.user.role != 'super_admin' and request.user.organization:
        templates = templates.filter(organization=request.user.organization) | templates.filter(organization__isnull=True)

    # Statistika
    total_sent = NotificationLog.objects.filter(is_deleted=False).count()
    total_unread = NotificationLog.objects.filter(is_deleted=False, status='sent').count()

    return render(request, 'automation/template_list.html', {
        'templates': templates,
        'total_sent': total_sent,
        'total_unread': total_unread,
    })


@login_required
def template_create(request):
    if request.method == 'POST':
        form = NotificationTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.organization = request.user.organization
            template.save()
            log_user_action(request.user, 'CREATE', 'NotificationTemplate', template.id, str(template), request=request)
            messages.success(request, "Shablon yaratildi!")
            return redirect('automation:template_list')
    else:
        form = NotificationTemplateForm()
    
    return render(request, 'automation/template_form.html', {'form': form, 'title': "Yangi Shablon"})


@login_required
def template_edit(request, pk):
    template = get_object_or_404(NotificationTemplate, pk=pk)
    # Check permissions
    if request.user.role != 'super_admin' and template.organization != request.user.organization:
        messages.error(request, "Ruxsat yo'q!")
        return redirect('automation:template_list')

    if request.method == 'POST':
        form = NotificationTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            log_user_action(request.user, 'UPDATE', 'NotificationTemplate', template.id, str(template), request=request)
            messages.success(request, "Shablon yangilandi!")
            return redirect('automation:template_list')
    else:
        form = NotificationTemplateForm(instance=template)
    
    return render(request, 'automation/template_form.html', {'form': form, 'title': "Shablonni tahrirlash"})


@login_required
def template_delete(request, pk):
    template = get_object_or_404(NotificationTemplate, pk=pk)
    if request.method == 'POST':
        template.is_deleted = True
        template.save()
        log_user_action(request.user, 'DELETE', 'NotificationTemplate', template.id, str(template), request=request)
        messages.success(request, "Shablon o'chirildi")
    return redirect('automation:template_list')


@login_required
def template_test(request, pk):
    """
    Shablonni test qilish - o'ziga xabar yuborish
    """
    template = get_object_or_404(NotificationTemplate, pk=pk)

    # Test xabarini o'ziga yuborish
    result = send_template_notification(
        user=request.user,
        template_code=template.code,
        context={
            'name': request.user.first_name,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'parent_name': 'Test Ota-ona',
            'student_name': 'Test O\'quvchi',
            'amount': '500,000',
            'balance': '1,200,000',
            'date': '13.02.2026',
            'group': 'IELTS-A1',
        }
    )

    if result:
        messages.success(request, f"Test xabari yuborildi! Bildirishnomalar bo'limini tekshiring.")
    else:
        messages.warning(request, f"Shablon topilmadi yoki xatolik yuz berdi.")

    return redirect('automation:template_list')


@login_required
def send_custom_notification(request):
    """
    Maxsus xabar yuborish (admin uchun)
    """
    if request.method == 'POST':
        title = request.POST.get('title', 'Yangi xabar')
        message = request.POST.get('message', '')
        recipient_id = request.POST.get('recipient')

        if recipient_id == 'all':
            # Barcha faol foydalanuvchilarga
            from apps.users.models import User
            recipients = User.objects.filter(is_active=True, organization=request.user.organization)
            count = 0
            for user in recipients:
                create_system_notification(user, title, message)
                count += 1
            messages.success(request, f"{count} ta foydalanuvchiga xabar yuborildi!")
        else:
            from apps.users.models import User
            try:
                recipient = User.objects.get(pk=recipient_id)
                create_system_notification(recipient, title, message)
                messages.success(request, f"{recipient.first_name} ga xabar yuborildi!")
            except User.DoesNotExist:
                messages.error(request, "Foydalanuvchi topilmadi!")

        return redirect('automation:template_list')

    # GET - forma ko'rsatish
    from apps.users.models import User
    users = User.objects.filter(is_active=True, organization=request.user.organization)
    return render(request, 'automation/send_notification.html', {'users': users})


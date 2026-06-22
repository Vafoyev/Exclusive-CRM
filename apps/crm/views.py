import json
import secrets
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Prefetch, Count
from asgiref.sync import sync_to_async

from .models import Lead, Stage, LeadSource, Activity
from .forms import LeadForm, StageForm, LeadSourceForm, LeadConvertForm
from .services import move_lead_to_stage
from apps.users.models import User, ParentStudent
from apps.core.audit import log_user_action
from apps.core.permissions import permission_required


# Async helper functions
@sync_to_async
def get_pipeline_data(org):
    """Pipeline ma'lumotlarini async olish"""
    from django.utils import timezone
    from django.db import models

    stages = Stage.objects.filter(organization=org, is_deleted=False) \
        .order_by('order') \
        .prefetch_related(
            Prefetch('leads', queryset=Lead.objects.filter(
                organization=org, is_deleted=False
            ).select_related('source', 'interested_course').order_by('-created_at'))
        ).annotate(
            lead_count=Count('leads', filter=models.Q(leads__is_deleted=False))
        )
    total_leads = Lead.objects.filter(organization=org, is_deleted=False).count()

    # Bugungi lidlar
    today = timezone.now().date()
    today_leads = Lead.objects.filter(
        organization=org,
        is_deleted=False,
        created_at__date=today
    ).count()

    # Manbalar
    sources = LeadSource.objects.filter(organization=org, is_deleted=False).annotate(
        lead_count=Count('lead', filter=~models.Q(lead__is_deleted=True))
    )

    return list(stages), total_leads, today_leads, list(sources)


# ===========================================
# PIPELINE (VORONKA)
# ===========================================

@login_required
@permission_required('crm', 'view')
def pipeline_view(request):
    """
    CRM Dashboard - Voronka, Bosqichlar va Manbalar.
    Barcha CRM ma'lumotlari bitta sahifada.
    """
    from django.db import models

    org = request.organization

    stages = Stage.objects.filter(organization=org, is_deleted=False) \
        .order_by('order') \
        .prefetch_related(
            Prefetch('leads', queryset=Lead.objects.filter(
                organization=org, is_deleted=False
            ).select_related('source', 'interested_course').order_by('-created_at'))
        ).annotate(
            lead_count=Count('leads', filter=models.Q(leads__is_deleted=False))
        )
    total_leads = Lead.objects.filter(organization=org, is_deleted=False).count()

    # Bugungi lidlar
    from django.utils import timezone
    today = timezone.now().date()
    today_leads = Lead.objects.filter(
        organization=org,
        is_deleted=False,
        created_at__date=today
    ).count()

    # Manbalar
    sources = LeadSource.objects.filter(organization=org, is_deleted=False).annotate(
        lead_count=Count('lead', filter=~models.Q(lead__is_deleted=True))
    )

    return render(request, 'crm/crm_dashboard.html', {
        'stages': stages,
        'total_leads': total_leads,
        'today_leads': today_leads,
        'sources': sources,
    })


# ===========================================
# LEADS (LIDLAR)
# ===========================================

@login_required
@permission_required('crm', 'create')
def lead_create(request):
    """Yangi Lid qo'shish"""
    org = request.organization
    
    if request.method == 'POST':
        form = LeadForm(request.POST, organization=org)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.organization = org

            # Avtomatik birinchi bosqichga qo'yamiz
            first_stage = Stage.objects.filter(
                organization=org, is_deleted=False
            ).order_by('order').first()
            
            if not first_stage:
                messages.error(request, "Avval bosqichlarni (Stages) yarating!")
                return redirect('crm:pipeline')

            lead.stage = first_stage
            lead.assigned_to = request.user
            lead.save()
            
            # Audit log
            log_user_action(request.user, 'CREATE', 'Lead', lead.id, str(lead), request=request)

            messages.success(request, "Lid muvaffaqiyatli qo'shildi!")
            return redirect('crm:pipeline')
    else:
        form = LeadForm(organization=org)

    return render(request, 'crm/lead_form.html', {'form': form, 'title': "Yangi Lid"})


@login_required
@permission_required('crm', 'view')
def lead_detail(request, pk):
    """Lid tafsilotlari"""
    org = request.organization
    lead = get_object_or_404(Lead, pk=pk, organization=org, is_deleted=False)
    
    # Activities
    activities = Activity.objects.filter(lead=lead).select_related('user').order_by('-created_at')
    
    # Bosqichlar (status o'zgartirish uchun)
    stages = Stage.objects.filter(organization=org, is_deleted=False).order_by('order')
    
    return render(request, 'crm/lead_detail.html', {
        'lead': lead,
        'activities': activities,
        'stages': stages,
    })


@login_required
@permission_required('crm', 'edit')
def lead_edit(request, pk):
    """Lidni tahrirlash"""
    org = request.organization
    lead = get_object_or_404(Lead, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        form = LeadForm(request.POST, instance=lead, organization=org)
        if form.is_valid():
            form.save()
            log_user_action(request.user, 'UPDATE', 'Lead', lead.id, str(lead), request=request)
            messages.success(request, "Lid yangilandi!")
            return redirect('lead_detail', pk=lead.pk)
    else:
        form = LeadForm(instance=lead, organization=org)
    
    return render(request, 'crm/lead_form.html', {'form': form, 'title': "Lidni tahrirlash", 'lead': lead})


@login_required
@permission_required('crm', 'delete')
def lead_delete(request, pk):
    """Lidni o'chirish (soft delete)"""
    org = request.organization
    lead = get_object_or_404(Lead, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        lead.delete()  # Soft delete
        log_user_action(request.user, 'DELETE', 'Lead', lead.id, str(lead), request=request)
        messages.warning(request, "Lid o'chirildi!")
        return redirect('crm:pipeline')
    
    return render(request, 'crm/lead_confirm_delete.html', {'lead': lead})


@login_required
@permission_required('crm', 'edit')
def lead_convert(request, pk):
    """Lidni o'quvchiga aylantirish"""
    org = request.organization
    lead = get_object_or_404(Lead, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        form = LeadConvertForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            
            # 1. Ota-onani yaratish
            parent, created = User.objects.get_or_create(
                phone=data['parent_phone'],
                defaults={
                    'first_name': data['parent_first_name'],
                    'last_name': data.get('parent_last_name', ''),
                    'role': 'parent',
                    'organization': org,
                }
            )
            if created:
                parent.set_password(secrets.token_urlsafe(8))
                parent.save()
            
            # 2. O'quvchini yaratish
            password = data.get('password') or secrets.token_urlsafe(8)
            student = User.objects.create(
                phone=data['phone'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                role='student',
                organization=org,
            )
            student.set_password(password)
            student.save()
            
            # 3. Ota-ona va o'quvchi bog'liqligi
            from .models import ParentStudent
            ParentStudent.objects.create(
                organization=org,
                parent=parent,
                student=student,
                relation_type=data['relation_type'],
                is_main_contact=True,
            )
            
            # 4. Lidni "Yutuq" bosqichiga o'tkazish
            from .models import Stage
            won_stage = Stage.objects.filter(organization=org, is_won=True).first()
            if won_stage:
                lead.stage = won_stage
                lead.save()
            
            # 5. Activity yozish
            Activity.objects.create(
                organization=org,
                lead=lead,
                user=request.user,
                activity_type='status_change',
                comment=f"O'quvchiga aylandi: {student.first_name} {student.last_name}"
            )
            
            # Audit log
            log_user_action(request.user, 'CREATE', 'User', student.id, str(student), 
                           changes={'converted_from_lead': lead.id}, request=request)
            
            messages.success(request, f"O'quvchi muvaffaqiyatli yaratildi! Parol: {password}")
            return redirect('users:user_list')
    else:
        # Formani lead ma'lumotlari bilan to'ldirish
        name_parts = lead.full_name.split(' ', 1)
        initial = {
            'first_name': name_parts[0] if name_parts else '',
            'last_name': name_parts[1] if len(name_parts) > 1 else '',
            'phone': lead.phone,
        }
        form = LeadConvertForm(initial=initial)
    
    return render(request, 'crm/lead_convert.html', {'form': form, 'lead': lead})


@require_POST
@login_required
@permission_required('crm', 'edit')
def update_lead_stage(request, lead_id):
    """API: JS orqali chaqiriladi (Drag & Drop bo'lganda)."""
    try:
        data = json.loads(request.body)
        new_stage_id = data.get('stage_id')

        # Servis orqali o'zgartiramiz (Log yozilishi uchun)
        move_lead_to_stage(lead_id, new_stage_id, request.user)
        
        # Audit log
        log_user_action(request.user, 'UPDATE', 'Lead', lead_id, 
                       changes={'stage_id': new_stage_id}, request=request)

        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@permission_required('crm', 'edit')
def add_lead_activity(request, pk):
    """Lidga yangi activity qo'shish"""
    org = request.organization
    lead = get_object_or_404(Lead, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        activity_type = request.POST.get('activity_type', 'note')
        comment = request.POST.get('comment', '')
        
        Activity.objects.create(
            organization=org,
            lead=lead,
            user=request.user,
            activity_type=activity_type,
            comment=comment,
        )
        messages.success(request, "Faoliyat qo'shildi!")
    
    return redirect('lead_detail', pk=pk)


# ===========================================
# STAGES (BOSQICHLAR)
# ===========================================

@login_required
@permission_required('crm', 'view')
def stage_list(request):
    """Bosqichlar ro'yxati"""
    org = request.organization
    stages = Stage.objects.filter(organization=org, is_deleted=False).annotate(
        lead_count=Count('leads', filter=models.Q(leads__is_deleted=False))
    ).order_by('order')
    
    return render(request, 'crm/stage_list.html', {'stages': stages})


@login_required
@permission_required('crm', 'create')
def stage_create(request):
    """Yangi bosqich yaratish"""
    org = request.organization
    
    if request.method == 'POST':
        form = StageForm(request.POST)
        if form.is_valid():
            stage = form.save(commit=False)
            stage.organization = org
            stage.save()
            log_user_action(request.user, 'CREATE', 'Stage', stage.id, str(stage), request=request)
            messages.success(request, "Bosqich yaratildi!")
            return redirect('crm:pipeline')
    else:
        # Default order
        max_order = Stage.objects.filter(organization=org).count() + 1
        form = StageForm(initial={'order': max_order, 'color': '#3B82F6'})
    
    return render(request, 'crm/stage_form.html', {'form': form, 'title': "Yangi Bosqich"})


@login_required
@permission_required('crm', 'edit')
def stage_edit(request, pk):
    """Bosqichni tahrirlash"""
    org = request.user.organization
    stage = get_object_or_404(Stage, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        form = StageForm(request.POST, instance=stage)
        if form.is_valid():
            form.save()
            log_user_action(request.user, 'UPDATE', 'Stage', stage.id, str(stage), request=request)
            messages.success(request, "Bosqich yangilandi!")
            return redirect('crm:pipeline')
    else:
        form = StageForm(instance=stage)
    
    return render(request, 'crm/stage_form.html', {'form': form, 'title': "Bosqichni tahrirlash"})


@login_required
@permission_required('crm', 'delete')
def stage_delete(request, pk):
    """Bosqichni o'chirish"""
    org = request.user.organization
    stage = get_object_or_404(Stage, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        # Tekshirish: bu bosqichda lidlar bormi?
        if stage.leads.filter(is_deleted=False).exists():
            messages.error(request, "Bu bosqichda lidlar bor! Avval ularni boshqa bosqichga o'tkazing.")
            return redirect('crm:pipeline')
        
        stage.delete()
        log_user_action(request.user, 'DELETE', 'Stage', stage.id, str(stage), request=request)
        messages.warning(request, "Bosqich o'chirildi!")
        return redirect('crm:pipeline')
    
    return render(request, 'crm/stage_confirm_delete.html', {'stage': stage})


# ===========================================
# SOURCES (MANBALAR)
# ===========================================

@login_required
@permission_required('crm', 'view')
def source_list(request):
    """Lid manbalari ro'yxati"""
    org = request.user.organization
    sources = LeadSource.objects.filter(organization=org, is_deleted=False).annotate(
        lead_count=Count('lead', filter=~models.Q(lead__is_deleted=True))
    )
    
    return render(request, 'crm/source_list.html', {'sources': sources})


@login_required
@permission_required('crm', 'create')
def source_create(request):
    """Yangi manba yaratish"""
    org = request.user.organization
    
    if request.method == 'POST':
        form = LeadSourceForm(request.POST)
        if form.is_valid():
            source = form.save(commit=False)
            source.organization = org
            source.save()
            log_user_action(request.user, 'CREATE', 'LeadSource', source.id, str(source), request=request)
            messages.success(request, "Manba yaratildi!")
            return redirect('crm:pipeline')
    else:
        form = LeadSourceForm()
    
    return render(request, 'crm/source_form.html', {'form': form, 'title': "Yangi Manba"})


@login_required
@permission_required('crm', 'edit')
def source_edit(request, pk):
    """Manbani tahrirlash"""
    org = request.user.organization
    source = get_object_or_404(LeadSource, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        form = LeadSourceForm(request.POST, instance=source)
        if form.is_valid():
            form.save()
            log_user_action(request.user, 'UPDATE', 'LeadSource', source.id, str(source), request=request)
            messages.success(request, "Manba yangilandi!")
            return redirect('crm:pipeline')
    else:
        form = LeadSourceForm(instance=source)
    
    return render(request, 'crm/source_form.html', {'form': form, 'title': "Manbani tahrirlash"})


@login_required
@permission_required('crm', 'delete')
def source_delete(request, pk):
    """Manbani o'chirish"""
    org = request.user.organization
    source = get_object_or_404(LeadSource, pk=pk, organization=org, is_deleted=False)
    
    if request.method == 'POST':
        source.delete()
        log_user_action(request.user, 'DELETE', 'LeadSource', source.id, str(source), request=request)
        messages.warning(request, "Manba o'chirildi!")
        return redirect('crm:pipeline')
    
    return render(request, 'crm/source_confirm_delete.html', {'source': source})


# Import models at top level to avoid circular imports
from django.db import models

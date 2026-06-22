"""
HTMX Views - Tez partial rendering.
Sahifani to'liq qayta yuklamasdan, faqat kerakli qismini yangilash.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.db import models

from .models import Lead, Stage


@login_required
@require_http_methods(["GET"])
def htmx_lead_card(request, pk):
    """
    Lid kartochkasini HTMX orqali yuklash.
    hx-get="/crm/htmx/lead/1/" hx-target="#lead-1"
    """
    lead = get_object_or_404(
        Lead.objects.select_related('source', 'interested_course', 'stage', 'assigned_to'),
        pk=pk, organization=request.organization, is_deleted=False
    )

    html = render_to_string('crm/partials/lead_card.html', {
        'lead': lead,
    }, request=request)

    return HttpResponse(html)


@login_required
@require_http_methods(["GET"])
def htmx_stage_leads(request, stage_id):
    """
    Bosqichdagi lidlarni HTMX orqali yuklash (lazy loading).
    hx-get="/crm/htmx/stage/1/leads/" hx-trigger="revealed"
    """
    stage = get_object_or_404(Stage, pk=stage_id, organization=request.organization, is_deleted=False)

    leads = Lead.objects.filter(
        stage=stage,
        organization=request.organization,
        is_deleted=False
    ).select_related('source', 'interested_course').order_by('-created_at')[:20]

    html = render_to_string('crm/partials/stage_leads.html', {
        'leads': leads,
        'stage': stage,
    }, request=request)

    return HttpResponse(html)


@login_required
@require_http_methods(["POST"])
def htmx_move_lead(request, pk, stage_id):
    """
    Lidni boshqa bosqichga ko'chirish (drag & drop).
    hx-post="/crm/htmx/lead/1/move/2/"
    """
    lead = get_object_or_404(Lead, pk=pk, organization=request.organization, is_deleted=False)
    new_stage = get_object_or_404(Stage, pk=stage_id, organization=request.organization, is_deleted=False)

    lead.stage = new_stage
    lead.save(update_fields=['stage', 'updated_at'])

    # Yangilangan kartochkani qaytarish
    html = render_to_string('crm/partials/lead_card.html', {
        'lead': lead,
    }, request=request)

    response = HttpResponse(html)
    response['HX-Trigger'] = 'leadMoved'
    return response


@login_required
@require_http_methods(["GET"])
def htmx_search_leads(request):
    """
    Lidlarni qidirish (debounced input).
    hx-get="/crm/htmx/search/" hx-trigger="keyup changed delay:300ms"
    """
    query = request.GET.get('q', '').strip()

    leads = Lead.objects.filter(
        organization=request.organization,
        is_deleted=False
    ).select_related('stage', 'source')

    if query:
        leads = leads.filter(
            models.Q(full_name__icontains=query) |
            models.Q(phone__icontains=query)
        )

    leads = leads[:10]

    html = render_to_string('crm/partials/search_results.html', {
        'leads': leads,
        'query': query,
    }, request=request)

    return HttpResponse(html)


@login_required
@require_http_methods(["DELETE"])
def htmx_delete_lead(request, pk):
    """
    Lidni o'chirish (soft delete).
    hx-delete="/crm/htmx/lead/1/" hx-confirm="Ishonchingiz komilmi?"
    """
    lead = get_object_or_404(Lead, pk=pk, organization=request.organization, is_deleted=False)
    lead.is_deleted = True
    lead.save(update_fields=['is_deleted', 'updated_at'])

    return HttpResponse('')

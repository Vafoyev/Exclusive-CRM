"""
Export va hisobot viewlari.
CSV, PDF eksport.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from datetime import date, timedelta
from apps.core.services import export_transactions_csv, get_financial_chart_data


@login_required
def export_transactions(request):
    """Tranzaksiyalarni CSV formatda yuklab olish"""
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    if start_date:
        start_date = date.fromisoformat(start_date)
    else:
        start_date = date.today().replace(day=1)
    
    if end_date:
        end_date = date.fromisoformat(end_date)
    else:
        end_date = date.today()
    
    csv_content = export_transactions_csv(
        request.user.organization,
        start_date,
        end_date
    )
    
    response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="transactions_{start_date}_{end_date}.csv"'
    
    return response


@login_required  
def api_chart_data(request):
    """Chart.js uchun JSON ma'lumotlar"""
    import json
    from django.http import JsonResponse
    
    days = int(request.GET.get('days', 30))
    chart_data = get_financial_chart_data(request.user.organization, days)
    
    return JsonResponse(chart_data)


@login_required
def global_search(request):
    """Global qidiruv"""
    from django.db.models import Q
    from apps.users.models import User
    from apps.crm.models import Lead
    from apps.education.models import Group
    
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return render(request, 'components/search_results.html', {'results': []})
    
    org = request.user.organization
    
    # Foydalanuvchilar
    users = User.objects.filter(
        organization=org
    ).filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(phone__icontains=query)
    )[:5]
    
    # Lidlar
    leads = Lead.objects.filter(
        organization=org
    ).filter(
        Q(name__icontains=query) |
        Q(phone__icontains=query)
    )[:5]
    
    # Guruhlar
    groups = Group.objects.filter(
        organization=org,
        name__icontains=query
    )[:5]
    
    results = []
    
    for user in users:
        results.append({
            'type': 'user',
            'icon': 'ph-user',
            'title': user.full_name,
            'subtitle': f"{user.get_role_display()} • {user.phone}",
            'url': f"/users/{user.id}/",
        })
    
    for lead in leads:
        results.append({
            'type': 'lead',
            'icon': 'ph-user-plus',
            'title': lead.name,
            'subtitle': f"Lead • {lead.phone}",
            'url': f"/crm/leads/{lead.id}/",
        })
    
    for group in groups:
        results.append({
            'type': 'group',
            'icon': 'ph-users-three',
            'title': group.name,
            'subtitle': f"Guruh • {group.get_status_display()}",
            'url': f"/education/groups/{group.id}/",
        })
    
    return render(request, 'components/search_results.html', {'results': results, 'query': query})

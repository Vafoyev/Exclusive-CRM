from collections import defaultdict
from datetime import timedelta, timezone as dt_timezone

from dateutil.parser import isoparse
from django.db import OperationalError, ProgrammingError
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from apps.finance.payroll import StaffAttendance
from apps.hardware.models import FaceIDEvent, FaceIDUserBinding
from apps.operations.models import Attendance


EVENT_TYPE_ALIASES = {
    'IN': 'CHECK_IN',
    'CHECKIN': 'CHECK_IN',
    'CHECK_IN': 'CHECK_IN',
    'OUT': 'CHECK_OUT',
    'CHECKOUT': 'CHECK_OUT',
    'CHECK_OUT': 'CHECK_OUT',
    'AUTO': 'AUTO',
    'TOGGLE': 'AUTO',
}

EVENT_TYPE_LABELS = {
    'CHECK_IN': "Markazga keldi",
    'CHECK_OUT': "Markazdan ketdi",
}

FACE_EVENT_DEBOUNCE_SECONDS = 60
STAFF_ROLES = {'super_admin', 'owner', 'admin', 'teacher', 'staff'}


def normalize_event_type(value, allow_auto=False):
    normalized = EVENT_TYPE_ALIASES.get(str(value or '').strip().upper())
    if normalized is None or (normalized == 'AUTO' and not allow_auto):
        raise ValueError("Noto'g'ri event turi.")
    return normalized


def get_event_type_label(value):
    return EVENT_TYPE_LABELS.get(str(value or '').strip().upper(), str(value or '').strip())


def parse_event_timestamp(value):
    event_dt = isoparse(value)
    if timezone.is_naive(event_dt):
        event_dt = timezone.make_aware(event_dt, timezone.get_current_timezone())
    return event_dt.astimezone(timezone.get_current_timezone())


def get_last_face_event_time(organization):
    return FaceIDEvent.objects.filter(organization=organization).aggregate(
        last_time=Max('occurred_at')
    )['last_time']


def get_previous_daily_face_event(organization, face_id_code, occurred_at):
    return FaceIDEvent.objects.filter(
        organization=organization,
        face_id_code=str(face_id_code),
        occurred_at__date=occurred_at.date(),
        occurred_at__lte=occurred_at,
    ).order_by('-occurred_at').first()


def resolve_daily_event_type(organization, face_id_code, occurred_at):
    """
    Entrance-style Hikvision flows often emit the same direction repeatedly.
    We treat the first pass of the day as arrival, then alternate arrival/exit.
    Very short repeated scans are considered the same pass.
    """
    previous_event = get_previous_daily_face_event(organization, face_id_code, occurred_at)
    if previous_event is None:
        return 'CHECK_IN', None, False

    delta_seconds = abs((occurred_at - previous_event.occurred_at).total_seconds())
    if delta_seconds <= FACE_EVENT_DEBOUNCE_SECONDS:
        return previous_event.event_type, previous_event, True

    next_event_type = 'CHECK_OUT' if previous_event.event_type == 'CHECK_IN' else 'CHECK_IN'
    return next_event_type, previous_event, False


def update_staff_attendance_from_event(user, event_type, occurred_at, organization):
    if user.role not in STAFF_ROLES:
        return None

    attendance, created = StaffAttendance.objects.get_or_create(
        staff=user,
        date=occurred_at.date(),
        defaults={
            'organization': organization,
            'expected_time': user.profile_data.get('work_start', '09:00') if user.profile_data else '09:00',
        }
    )

    changed_fields = []
    event_time = occurred_at.timetz().replace(tzinfo=None)

    if event_type == 'CHECK_IN':
        if attendance.check_in is None or event_time < attendance.check_in:
            attendance.check_in = event_time
            changed_fields.append('check_in')
        attendance.nfc_check_in = True
        if 'nfc_check_in' not in changed_fields:
            changed_fields.append('nfc_check_in')
        attendance.calculate_late_minutes()
        for field in ('late_minutes', 'status'):
            if field not in changed_fields:
                changed_fields.append(field)
    else:
        if attendance.check_out is None or event_time > attendance.check_out:
            attendance.check_out = event_time
            changed_fields.append('check_out')
        attendance.nfc_check_out = True
        if 'nfc_check_out' not in changed_fields:
            changed_fields.append('nfc_check_out')
        if attendance.status == 'absent':
            attendance.status = 'present'
            changed_fields.append('status')

    note = "Hikvision Face ID"
    if attendance.notes != note:
        attendance.notes = note
        changed_fields.append('notes')

    if created:
        attendance.save()
    elif changed_fields:
        attendance.save(update_fields=changed_fields)

    return attendance


@transaction.atomic
def register_face_event(integration, face_id_code, event_type, timestamp, device_ip=None, raw_payload=None):
    normalize_event_type(event_type, allow_auto=True)
    occurred_at = parse_event_timestamp(timestamp)
    resolved_event_type, previous_event, is_duplicate_scan = resolve_daily_event_type(
        integration.organization,
        face_id_code,
        occurred_at,
    )
    binding = FaceIDUserBinding.objects.select_related('user').filter(
        organization=integration.organization,
        face_id_code=str(face_id_code),
    ).first()

    if is_duplicate_scan and previous_event is not None:
        event = previous_event
        created = False
    else:
        event, created = FaceIDEvent.objects.get_or_create(
            organization=integration.organization,
            face_id_code=str(face_id_code),
            event_type=resolved_event_type,
            occurred_at=occurred_at,
            defaults={
                'user': binding.user if binding else None,
                'device_ip': device_ip,
                'raw_payload': raw_payload or {},
            }
        )

    if not created and not is_duplicate_scan:
        updated_fields = []
        if event.user_id is None and binding is not None:
            event.user = binding.user
            updated_fields.append('user')
        if device_ip and event.device_ip != device_ip:
            event.device_ip = device_ip
            updated_fields.append('device_ip')
        if raw_payload and event.raw_payload != raw_payload:
            event.raw_payload = raw_payload
            updated_fields.append('raw_payload')
        if updated_fields:
            event.save(update_fields=updated_fields)

    if binding is not None:
        update_fields = []
        if binding.last_event_at is None or occurred_at >= binding.last_event_at:
            binding.last_event_at = occurred_at
            binding.last_event_type = resolved_event_type
            update_fields.extend(['last_event_at', 'last_event_type'])
            if device_ip:
                binding.last_device_ip = device_ip
                update_fields.append('last_device_ip')
        elif device_ip and not binding.last_device_ip:
            binding.last_device_ip = device_ip
            update_fields.append('last_device_ip')

        if update_fields:
            binding.save(update_fields=update_fields)

        if not is_duplicate_scan:
            update_staff_attendance_from_event(binding.user, resolved_event_type, occurred_at, integration.organization)

    integration.last_event_received_at = timezone.now()
    integration.save(update_fields=['last_event_received_at'])

    return event, created


def last_event_time_as_utc_string(organization):
    last_event = get_last_face_event_time(organization)
    if not last_event:
        return None
    return last_event.astimezone(dt_timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _empty_student_presence_payload():
    return {
        'present_lessons_count': 0,
        'missed_lessons_count': 0,
        'late_lessons_count': 0,
        'today_presence': None,
        'recent_face_logs': [],
    }


def build_student_presence_map(student_ids, days=7):
    """
    Studentlar uchun qoldirilgan darslar va markazga kelib-ketish summary.
    Face ID jadvallari hali migratsiya qilinmagan bo'lsa, xavfsiz ravishda bo'sh data qaytaradi.
    """
    unique_student_ids = [student_id for student_id in dict.fromkeys(student_ids) if student_id]
    if not unique_student_ids:
        return {}

    presence_map = {student_id: _empty_student_presence_payload() for student_id in unique_student_ids}

    attendance_stats = {
        row['student_id']: row
        for row in Attendance.objects.filter(student_id__in=unique_student_ids).values('student_id').annotate(
            present_lessons_count=Count('id', filter=Q(status='present')),
            missed_lessons_count=Count('id', filter=Q(status__in=['absent', 'excused'])),
            late_lessons_count=Count('id', filter=Q(status='late')),
        )
    }
    for student_id, payload in presence_map.items():
        stats = attendance_stats.get(student_id, {})
        payload['present_lessons_count'] = stats.get('present_lessons_count') or 0
        payload['missed_lessons_count'] = stats.get('missed_lessons_count') or 0
        payload['late_lessons_count'] = stats.get('late_lessons_count') or 0

    today = timezone.localdate()
    start_date = today - timedelta(days=max(days - 1, 0))
    try:
        face_events = FaceIDEvent.objects.filter(
            user_id__in=unique_student_ids,
            occurred_at__date__gte=start_date,
        ).only(
            'user_id', 'event_type', 'occurred_at',
        ).order_by(
            'user_id', '-occurred_at',
        )
    except (ProgrammingError, OperationalError):
        return presence_map

    grouped_logs = defaultdict(dict)
    for event in face_events:
        user_logs = grouped_logs[event.user_id]
        event_date = timezone.localtime(event.occurred_at).date()
        day_summary = user_logs.setdefault(event_date, {
            'date': event_date,
            'check_in_at': None,
            'check_out_at': None,
        })
        local_dt = timezone.localtime(event.occurred_at)
        if event.event_type == 'CHECK_IN':
            if day_summary['check_in_at'] is None or local_dt < day_summary['check_in_at']:
                day_summary['check_in_at'] = local_dt
        elif event.event_type == 'CHECK_OUT':
            if day_summary['check_out_at'] is None or local_dt > day_summary['check_out_at']:
                day_summary['check_out_at'] = local_dt

    for student_id, daily_logs in grouped_logs.items():
        sorted_logs = sorted(daily_logs.values(), key=lambda item: item['date'], reverse=True)
        presence_map[student_id]['recent_face_logs'] = sorted_logs[:days]
        presence_map[student_id]['today_presence'] = next(
            (item for item in sorted_logs if item['date'] == today),
            None,
        )

    return presence_map

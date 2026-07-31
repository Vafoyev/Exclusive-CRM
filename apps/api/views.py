"""
API viewlari.
Umumiy, Ota-ona va O'quvchi endpointlari.
"""
from datetime import timedelta

from django.db.models import Avg, Count, F, Q, Sum, Window
from django.db.models.functions import RowNumber
from django.utils import timezone
from rest_framework import viewsets, permissions, generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.views import ObtainAuthToken
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.users.models import User, ParentStudent
from apps.education.models import GroupStudent
from apps.operations.models import Lesson, Attendance
from apps.operations.shop import ShopItem
from apps.finance.models import Transaction
from apps.hardware.services import build_student_presence_map

from .permissions import IsParent, IsStudent
from apps.core.permissions import IsOwnerOrAdmin
from .serializers import (
    UserSerializer,
    TransactionSerializer,
    EnrollmentSerializer,
    LessonSerializer,
    AttendanceSerializer,
    ChildAttendanceSerializer,
    PaymentSerializer,
    ChildDetailSerializer,
    ParentDashboardSerializer,
    LeaderboardEntrySerializer,
    StudentStatsSerializer,
    StudentDashboardSerializer,
)


# ============================================
# AUTENTIFIKATSIYA
# ============================================

class CustomObtainAuthToken(ObtainAuthToken):
    """Token olish uchun autentifikatsiya endpoint."""

    @extend_schema(tags=["Autentifikatsiya"], summary="Token olish", description="Foydalanuvchi nomi va parol orqali autentifikatsiya tokeni olish.")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


# ============================================
# UMUMIY VIEWLAR (mavjud)
# ============================================

@extend_schema_view(
    list=extend_schema(tags=["Foydalanuvchilar"], summary="Foydalanuvchilar ro'yxati", description="Barcha foydalanuvchilarni ko'rish. Super admin barcha foydalanuvchilarni, boshqalar faqat o'z tashkilotidagilarni ko'radi."),
    retrieve=extend_schema(tags=["Foydalanuvchilar"], summary="Foydalanuvchi tafsilotlari", description="Bitta foydalanuvchi haqida batafsil ma'lumot."),
)
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'super_admin':
            return User.objects.all()
        return User.objects.filter(organization=user.organization)


@extend_schema_view(
    list=extend_schema(tags=["Tranzaksiyalar"], summary="Tranzaksiyalar ro'yxati", description="Barcha tranzaksiyalarni ko'rish."),
    retrieve=extend_schema(tags=["Tranzaksiyalar"], summary="Tranzaksiya tafsilotlari", description="Bitta tranzaksiya haqida batafsil ma'lumot."),
    create=extend_schema(tags=["Tranzaksiyalar"], summary="Yangi tranzaksiya yaratish", description="Yangi to'lov yoki tranzaksiya qo'shish."),
    update=extend_schema(tags=["Tranzaksiyalar"], summary="Tranzaksiyani yangilash", description="Mavjud tranzaksiyani to'liq yangilash."),
    partial_update=extend_schema(tags=["Tranzaksiyalar"], summary="Tranzaksiyani qisman yangilash", description="Mavjud tranzaksiyani qisman yangilash."),
    destroy=extend_schema(tags=["Tranzaksiyalar"], summary="Tranzaksiyani o'chirish", description="Tranzaksiyani o'chirish."),
)
class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'super_admin':
            return Transaction.objects.all()
        return Transaction.objects.filter(organization=user.organization)

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            organization=self.request.user.organization,
            status='pending',
            receipt_verified=False,
        )


# ============================================
# OTA-ONA (PARENT) API
# ============================================

def _build_child_data(child):
    """Bitta farzand uchun dashboard ma'lumotlarini yig'adi."""
    enrollments = GroupStudent.objects.filter(
        student=child, status='active',
    ).select_related('group', 'group__course', 'group__teacher', 'group__room')

    stats = Attendance.objects.filter(student=child).aggregate(
        total_att=Count('id'),
        present=Count('id', filter=Q(status='present')),
        avg_grade=Avg('grade'),
        total_xp=Sum('xp_points'),
    )
    total_att = stats['total_att'] or 0
    present = stats['present'] or 0
    att_rate = (present / total_att * 100) if total_att > 0 else 0
    avg_grade = stats['avg_grade'] or 0

    recent_attendance = Attendance.objects.filter(
        student=child,
    ).select_related('lesson', 'lesson__group').order_by('-lesson__date')[:5]
    presence_summary = build_student_presence_map([child.id]).get(child.id, {})

    return {
        'child': child,
        'relation_type': '',
        'enrollments': enrollments,
        'attendance_rate': round(att_rate, 1),
        'avg_grade': round(float(avg_grade), 1),
        'balance': child.balance,
        'has_debt': child.balance < 0,
        'xp': stats['total_xp'] or 0,
        'missed_lessons_count': presence_summary.get('missed_lessons_count', 0),
        'today_presence': presence_summary.get('today_presence'),
        'recent_face_logs': presence_summary.get('recent_face_logs', []),
        'recent_attendance': recent_attendance,
    }


def _build_children_payload(relations):
    relations = list(relations)
    if not relations:
        return []

    child_ids = [relation.student_id for relation in relations]
    student_presence_map = build_student_presence_map(child_ids)

    enrollments_map = {child_id: [] for child_id in child_ids}
    for enrollment in GroupStudent.objects.filter(
        student_id__in=child_ids,
        status='active',
    ).select_related('group', 'group__course', 'group__teacher', 'group__room'):
        enrollments_map.setdefault(enrollment.student_id, []).append(enrollment)

    stats_map = {
        row['student_id']: row
        for row in Attendance.objects.filter(
            student_id__in=child_ids,
        ).values('student_id').annotate(
            total_att=Count('id'),
            present=Count('id', filter=Q(status='present')),
            avg_grade=Avg('grade'),
            total_xp=Sum('xp_points'),
        )
    }

    recent_attendance_map = {child_id: [] for child_id in child_ids}
    for attendance in Attendance.objects.filter(
        student_id__in=child_ids,
    ).annotate(
        row_number=Window(
            expression=RowNumber(),
            partition_by=[F('student_id')],
            order_by=[F('lesson__date').desc(), F('id').desc()],
        )
    ).filter(
        row_number__lte=5,
    ).select_related(
        'lesson', 'lesson__group',
    ).order_by(
        'student_id', '-lesson__date', '-id',
    ):
        recent_attendance_map.setdefault(attendance.student_id, []).append(attendance)

    children = []
    for relation in relations:
        child = relation.student
        stats = stats_map.get(child.id, {})
        total_att = stats.get('total_att') or 0
        present = stats.get('present') or 0
        att_rate = (present / total_att * 100) if total_att > 0 else 0
        avg_grade = stats.get('avg_grade') or 0

        children.append({
            'child': child,
            'relation_type': relation.get_relation_type_display(),
            'enrollments': enrollments_map.get(child.id, []),
            'attendance_rate': round(att_rate, 1),
            'avg_grade': round(float(avg_grade), 1),
            'balance': child.balance,
            'has_debt': child.balance < 0,
            'xp': stats.get('total_xp') or 0,
            'missed_lessons_count': student_presence_map.get(child.id, {}).get('missed_lessons_count', 0),
            'today_presence': student_presence_map.get(child.id, {}).get('today_presence'),
            'recent_face_logs': student_presence_map.get(child.id, {}).get('recent_face_logs', []),
            'recent_attendance': recent_attendance_map.get(child.id, []),
        })

    return children


class ParentDashboardView(APIView):
    """
    GET /api/parent/dashboard/
    Ota-ona dashboardi - barcha farzandlari haqida umumiy ma'lumot.
    """
    permission_classes = [permissions.IsAuthenticated, IsParent]

    @extend_schema(tags=["Ota-ona"], summary="Ota-ona dashboardi", description="Barcha farzandlar haqida umumiy ma'lumot: davomat, baholar, balans va qarzlar.", responses=ParentDashboardSerializer)
    def get(self, request):
        parent = request.user
        relations = ParentStudent.objects.filter(
            parent=parent,
        ).select_related('student')

        children = _build_children_payload(relations)

        total_debt = sum(
            abs(c['balance']) for c in children if c['has_debt']
        )
        has_any_debt = any(c['has_debt'] for c in children)

        serializer = ParentDashboardSerializer({
            'children': children,
            'total_debt': total_debt,
            'has_any_debt': has_any_debt,
        })
        return Response(serializer.data)


@extend_schema(tags=["Ota-ona"], summary="Farzandlar ro'yxati", description="Ota-onaning barcha farzandlari ro'yxati va ularning ma'lumotlari.", responses=ChildDetailSerializer(many=True))
class ParentChildrenListView(APIView):
    """
    GET /api/parent/children/
    Ota-onaning barcha farzandlari ro'yxati.
    """
    permission_classes = [permissions.IsAuthenticated, IsParent]

    def get(self, request):
        relations = ParentStudent.objects.filter(
            parent=request.user,
        ).select_related('student')

        children = _build_children_payload(relations)

        serializer = ChildDetailSerializer(children, many=True)
        return Response(serializer.data)


@extend_schema(tags=["Ota-ona"], summary="Farzand tafsilotlari", description="Bitta farzand haqida batafsil ma'lumot: guruhlar, davomat, baholar.", responses=ChildDetailSerializer)
class ParentChildDetailView(APIView):
    """
    GET /api/parent/children/<child_id>/
    Bitta farzand haqida batafsil ma'lumot.
    """
    permission_classes = [permissions.IsAuthenticated, IsParent]

    def get(self, request, child_id):
        relation = ParentStudent.objects.filter(
            parent=request.user, student_id=child_id,
        ).select_related('student').first()

        if not relation:
            return Response(
                {'detail': 'Farzand topilmadi.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = _build_child_data(relation.student)
        data['relation_type'] = relation.get_relation_type_display()

        serializer = ChildDetailSerializer(data)
        return Response(serializer.data)


@extend_schema(tags=["Ota-ona"], summary="Farzand davomati", description="Farzandning davomati (sahifalangan ro'yxat).")
class ParentChildAttendanceView(generics.ListAPIView):
    """
    GET /api/parent/children/<child_id>/attendance/
    Farzandning davomati (sahifalangan).
    """
    serializer_class = ChildAttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsParent]

    def get_queryset(self):
        child_id = self.kwargs['child_id']
        is_related = ParentStudent.objects.filter(
            parent=self.request.user, student_id=child_id,
        ).exists()
        if not is_related:
            return Attendance.objects.none()
        return Attendance.objects.filter(
            student_id=child_id,
        ).select_related('lesson', 'lesson__group').order_by('-lesson__date')


@extend_schema(tags=["Ota-ona"], summary="Farzand to'lovlari", description="Farzandning to'lov tarixi (sahifalangan ro'yxat).")
class ParentChildPaymentsView(generics.ListAPIView):
    """
    GET /api/parent/children/<child_id>/payments/
    Farzandning to'lov tarixi (sahifalangan).
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsParent]

    def get_queryset(self):
        child_id = self.kwargs['child_id']
        is_related = ParentStudent.objects.filter(
            parent=self.request.user, student_id=child_id,
        ).exists()
        if not is_related:
            return Transaction.objects.none()
        return Transaction.objects.filter(
            student_id=child_id,
        ).order_by('-created_at')


# ============================================
# O'QUVCHI (STUDENT) API
# ============================================

def _build_student_stats(student):
    """O'quvchi statistikasini hisoblaydi."""
    stats = Attendance.objects.filter(student=student).aggregate(
        total_lessons=Count('id'),
        present_count=Count('id', filter=Q(status='present')),
        avg_grade=Avg('grade'),
        total_xp=Sum('xp_points'),
    )
    total_lessons = stats['total_lessons'] or 0
    present_count = stats['present_count'] or 0
    attendance_rate = (present_count / total_lessons * 100) if total_lessons > 0 else 0
    avg_grade = stats['avg_grade'] or 0
    total_xp = stats['total_xp'] or 0

    coin_balance = total_xp
    if hasattr(student, 'profile_data') and student.profile_data:
        coin_balance = student.profile_data.get('xp', total_xp)
    presence_summary = build_student_presence_map([student.id]).get(student.id, {})

    return {
        'attendance_rate': round(attendance_rate, 1),
        'avg_grade': round(float(avg_grade), 1),
        'total_xp': total_xp,
        'coin_balance': coin_balance,
        'balance': student.balance,
        'missed_lessons_count': presence_summary.get('missed_lessons_count', 0),
        'late_lessons_count': presence_summary.get('late_lessons_count', 0),
    }


def _build_leaderboard(student):
    """Tashkilot bo'yicha XP reytingi."""
    org = student.organization
    if not org:
        return [], 0

    ranked_students = User.objects.filter(
        role='student',
        organization=org,
        is_active=True,
        is_deleted=False,
    ).annotate(
        xp_total=Sum('lesson_attendances__xp_points'),
    ).exclude(
        xp_total__isnull=True,
    ).annotate(
        rank=Window(
            expression=RowNumber(),
            order_by=[F('xp_total').desc(), F('id').asc()],
        )
    ).order_by('rank')

    leaderboard = list(ranked_students[:10])
    student_rank = ranked_students.filter(id=student.id).values_list('rank', flat=True).first() or 0

    return leaderboard, student_rank


class StudentDashboardView(APIView):
    """
    GET /api/student/dashboard/
    O'quvchi dashboardi - barcha ma'lumotlar.
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @extend_schema(tags=["O'quvchi"], summary="O'quvchi dashboardi", description="O'quvchining barcha ma'lumotlari: guruhlar, darslar, davomat, to'lovlar, reyting va statistika.", responses=StudentDashboardSerializer)
    def get(self, request):
        student = request.user
        today = timezone.now().date()

        # Guruhlarim
        enrollments = GroupStudent.objects.filter(
            student=student, status='active',
        ).select_related(
            'group', 'group__course', 'group__teacher', 'group__room',
        )
        group_ids = enrollments.values_list('group_id', flat=True)

        # Bugungi darslar
        today_lessons = Lesson.objects.filter(
            group_id__in=group_ids, date=today,
        ).select_related('group', 'teacher', 'room').order_by('start_time')

        # Keyingi darslar
        upcoming_lessons = Lesson.objects.filter(
            group_id__in=group_ids, date__gt=today,
        ).select_related('group', 'teacher', 'room').order_by(
            'date', 'start_time',
        )[:10]

        # So'nggi davomat
        recent_attendance = Attendance.objects.filter(
            student=student,
        ).select_related('lesson', 'lesson__group').order_by('-lesson__date')[:20]
        presence_summary = build_student_presence_map([student.id]).get(student.id, {})

        # Statistikalar
        stats = _build_student_stats(student)

        # To'lovlar
        payments = Transaction.objects.filter(
            student=student,
        ).select_related('account', 'category', 'confirmed_by').order_by('-created_at')[:10]

        # Chart Data (So'nggi 10 ta baho - DB darajasida)
        grade_history = list(
            Attendance.objects.filter(
                student=student, grade__isnull=False,
            ).select_related('lesson').order_by('-lesson__date')[:10]
        )
        grade_history.reverse()
        chart_labels = [att.lesson.date.strftime('%d.%m') for att in grade_history]
        chart_data = [att.grade for att in grade_history]

        # Leaderboard
        leaderboard, student_rank = _build_leaderboard(student)

        # Shop
        org = student.organization
        shop_items_count = 0
        if org:
            shop_items_count = ShopItem.objects.filter(
                organization=org, is_active=True, is_deleted=False,
            ).count()

        serializer = StudentDashboardSerializer({
            'stats': stats,
            'enrollments': enrollments,
            'today_lessons': today_lessons,
            'upcoming_lessons': upcoming_lessons,
            'recent_attendance': recent_attendance,
            'today_presence': presence_summary.get('today_presence'),
            'recent_face_logs': presence_summary.get('recent_face_logs', []),
            'recent_payments': payments,
            'chart_labels': chart_labels,
            'chart_data': chart_data,
            'leaderboard': leaderboard,
            'student_rank': student_rank,
            'shop_items_count': shop_items_count,
        })
        return Response(serializer.data)


@extend_schema(tags=["O'quvchi"], summary="O'quvchi guruhlari", description="O'quvchi a'zo bo'lgan barcha aktiv guruhlar ro'yxati.")
class StudentEnrollmentsView(generics.ListAPIView):
    """
    GET /api/student/enrollments/
    O'quvchining guruhlari.
    """
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        return GroupStudent.objects.filter(
            student=self.request.user, status='active',
        ).select_related(
            'group', 'group__course', 'group__teacher', 'group__room',
        ).order_by('-joined_at', '-id')


@extend_schema(tags=["O'quvchi"], summary='Bugungi darslar', description="O'quvchining bugungi kun uchun rejalashtirilgan darslari.")
class StudentTodayLessonsView(generics.ListAPIView):
    """
    GET /api/student/lessons/today/
    Bugungi darslar.
    """
    serializer_class = LessonSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        student = self.request.user
        today = timezone.now().date()
        my_groups = GroupStudent.objects.filter(
            student=student, status='active',
        ).values_list('group_id', flat=True)
        return Lesson.objects.filter(
            group_id__in=my_groups, date=today,
        ).select_related('group', 'teacher', 'room').order_by('start_time')


@extend_schema(tags=["O'quvchi"], summary='Kelgusi darslar', description="O'quvchining kelgusi rejalashtirilgan darslari (20 tagacha).")
class StudentUpcomingLessonsView(generics.ListAPIView):
    """
    GET /api/student/lessons/upcoming/
    Kelgusi darslar.
    """
    serializer_class = LessonSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        student = self.request.user
        today = timezone.now().date()
        my_groups = GroupStudent.objects.filter(
            student=student, status='active',
        ).values_list('group_id', flat=True)
        return Lesson.objects.filter(
            group_id__in=my_groups, date__gt=today,
        ).select_related('group', 'teacher', 'room').order_by(
            'date', 'start_time',
        )[:20]


@extend_schema(tags=["O'quvchi"], summary="O'quvchi davomati", description="O'quvchining davomati (sahifalangan ro'yxat).")
class StudentAttendanceView(generics.ListAPIView):
    """
    GET /api/student/attendance/
    O'quvchining davomati (sahifalangan).
    """
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        return Attendance.objects.filter(
            student=self.request.user,
        ).select_related('lesson', 'lesson__group').order_by('-lesson__date')


@extend_schema(tags=["O'quvchi"], summary="O'quvchi to'lovlari", description="O'quvchining to'lov tarixi (sahifalangan ro'yxat).")
class StudentPaymentsView(generics.ListAPIView):
    """
    GET /api/student/payments/
    O'quvchining to'lov tarixi (sahifalangan).
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        return Transaction.objects.filter(
            student=self.request.user,
        ).order_by('-created_at')


class StudentLeaderboardView(APIView):
    """
    GET /api/student/leaderboard/
    XP bo'yicha reyting jadvali.
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @extend_schema(tags=["O'quvchi"], summary='XP reyting jadvali', description="Tashkilot bo'yicha XP reytingi - top 10 o'quvchi va joriy o'quvchining o'rni.", responses=LeaderboardEntrySerializer(many=True))
    def get(self, request):
        leaderboard, student_rank = _build_leaderboard(request.user)
        serializer = LeaderboardEntrySerializer(leaderboard, many=True)
        return Response({
            'leaderboard': serializer.data,
            'student_rank': student_rank,
        })


class StudentStatsView(APIView):
    """
    GET /api/student/stats/
    O'quvchining statistikasi.
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @extend_schema(tags=["O'quvchi"], summary="O'quvchi statistikasi", description="O'quvchining umumiy statistikasi: davomat foizi, o'rtacha baho, XP va balans.", responses=StudentStatsSerializer)
    def get(self, request):
        stats = _build_student_stats(request.user)
        serializer = StudentStatsSerializer(stats)
        return Response(serializer.data)

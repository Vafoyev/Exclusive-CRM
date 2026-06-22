from rest_framework import serializers
from apps.users.models import User, ParentStudent
from apps.education.models import Course, Group, GroupStudent, Room
from apps.operations.models import Lesson, Attendance
from apps.finance.models import Transaction


# ============================================
# UMUMIY SERIALIZERLAR
# ============================================

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'phone', 'role', 'balance', 'avatar']


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'


class UserBriefSerializer(serializers.ModelSerializer):
    """Foydalanuvchi qisqa ma'lumotlari."""
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'full_name', 'phone', 'avatar']


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['id', 'name', 'capacity']


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['id', 'name', 'description', 'price', 'duration_months']


class GroupSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    teacher = UserBriefSerializer(read_only=True)
    room = RoomSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Group
        fields = [
            'id', 'name', 'course', 'teacher', 'room', 'status',
            'status_display', 'start_date', 'end_date',
            'schedule_days', 'start_time', 'end_time',
        ]


class LessonSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    teacher = UserBriefSerializer(read_only=True)
    room = RoomSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Lesson
        fields = [
            'id', 'group_name', 'teacher', 'room', 'date',
            'start_time', 'end_time', 'topic', 'status', 'status_display',
        ]


class AttendanceSerializer(serializers.ModelSerializer):
    lesson_date = serializers.DateField(source='lesson.date', read_only=True)
    group_name = serializers.CharField(source='lesson.group.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Attendance
        fields = [
            'id', 'lesson_date', 'group_name', 'status',
            'status_display', 'grade', 'xp_points', 'comment',
        ]


class EnrollmentSerializer(serializers.ModelSerializer):
    group = GroupSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = GroupStudent
        fields = ['id', 'group', 'joined_at', 'status', 'status_display']


class PaymentSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display', read_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(
        source='get_payment_method_display', read_only=True
    )

    class Meta:
        model = Transaction
        fields = [
            'id', 'amount', 'transaction_type', 'transaction_type_display',
            'status', 'status_display', 'payment_method',
            'payment_method_display', 'description', 'created_at',
        ]


# ============================================
# OTA-ONA (PARENT) SERIALIZERLARI
# ============================================

class ChildAttendanceSerializer(serializers.ModelSerializer):
    """Farzand davomati."""
    lesson_date = serializers.DateField(source='lesson.date', read_only=True)
    lesson_start_time = serializers.TimeField(source='lesson.start_time', read_only=True)
    group_name = serializers.CharField(source='lesson.group.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Attendance
        fields = [
            'id', 'lesson_date', 'lesson_start_time', 'group_name',
            'status', 'status_display', 'grade', 'xp_points', 'comment',
        ]


class FacePresenceLogSerializer(serializers.Serializer):
    date = serializers.DateField()
    check_in_at = serializers.DateTimeField(allow_null=True)
    check_out_at = serializers.DateTimeField(allow_null=True)


class ChildDetailSerializer(serializers.Serializer):
    """Farzand haqida to'liq ma'lumot."""
    child = UserSerializer()
    relation_type = serializers.CharField()
    enrollments = EnrollmentSerializer(many=True)
    attendance_rate = serializers.FloatField()
    avg_grade = serializers.FloatField()
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    has_debt = serializers.BooleanField()
    xp = serializers.IntegerField()
    missed_lessons_count = serializers.IntegerField()
    today_presence = FacePresenceLogSerializer(allow_null=True)
    recent_face_logs = FacePresenceLogSerializer(many=True)
    recent_attendance = ChildAttendanceSerializer(many=True)


class ParentDashboardSerializer(serializers.Serializer):
    """Ota-ona dashboardi."""
    children = ChildDetailSerializer(many=True)
    total_debt = serializers.DecimalField(max_digits=12, decimal_places=2)
    has_any_debt = serializers.BooleanField()


# ============================================
# O'QUVCHI (STUDENT) SERIALIZERLARI
# ============================================

class LeaderboardEntrySerializer(serializers.ModelSerializer):
    """Reyting ro'yxatidagi o'quvchi."""
    full_name = serializers.CharField(read_only=True)
    xp_total = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'full_name', 'avatar', 'xp_total']


class StudentStatsSerializer(serializers.Serializer):
    """O'quvchi statistikasi."""
    attendance_rate = serializers.FloatField()
    avg_grade = serializers.FloatField()
    total_xp = serializers.IntegerField()
    coin_balance = serializers.IntegerField()
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    missed_lessons_count = serializers.IntegerField()
    late_lessons_count = serializers.IntegerField()


class StudentDashboardSerializer(serializers.Serializer):
    """O'quvchi dashboardi."""
    stats = StudentStatsSerializer()
    enrollments = EnrollmentSerializer(many=True)
    today_lessons = LessonSerializer(many=True)
    upcoming_lessons = LessonSerializer(many=True)
    recent_attendance = AttendanceSerializer(many=True)
    today_presence = FacePresenceLogSerializer(allow_null=True)
    recent_face_logs = FacePresenceLogSerializer(many=True)
    recent_payments = PaymentSerializer(many=True)
    chart_labels = serializers.ListField(child=serializers.CharField())
    chart_data = serializers.ListField(child=serializers.IntegerField())
    leaderboard = LeaderboardEntrySerializer(many=True)
    student_rank = serializers.IntegerField()
    shop_items_count = serializers.IntegerField()

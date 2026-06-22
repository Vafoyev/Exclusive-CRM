from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomObtainAuthToken,
    UserViewSet,
    TransactionViewSet,
    # Parent
    ParentDashboardView,
    ParentChildrenListView,
    ParentChildDetailView,
    ParentChildAttendanceView,
    ParentChildPaymentsView,
    # Student
    StudentDashboardView,
    StudentEnrollmentsView,
    StudentTodayLessonsView,
    StudentUpcomingLessonsView,
    StudentAttendanceView,
    StudentPaymentsView,
    StudentLeaderboardView,
    StudentStatsView,
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'transactions', TransactionViewSet)

urlpatterns = [
    path('', include(router.urls)),

    # ====== AUTENTIFIKATSIYA ======
    path('auth/token/', CustomObtainAuthToken.as_view(), name='api-token-auth'),

    # ====== OTA-ONA (PARENT) ======
    path('parent/dashboard/', ParentDashboardView.as_view(), name='parent-dashboard'),
    path('parent/children/', ParentChildrenListView.as_view(), name='parent-children-list'),
    path('parent/children/<int:child_id>/', ParentChildDetailView.as_view(), name='parent-child-detail'),
    path('parent/children/<int:child_id>/attendance/', ParentChildAttendanceView.as_view(), name='parent-child-attendance'),
    path('parent/children/<int:child_id>/payments/', ParentChildPaymentsView.as_view(), name='parent-child-payments'),

    # ====== O'QUVCHI (STUDENT) ======
    path('student/dashboard/', StudentDashboardView.as_view(), name='student-dashboard'),
    path('student/enrollments/', StudentEnrollmentsView.as_view(), name='student-enrollments'),
    path('student/lessons/today/', StudentTodayLessonsView.as_view(), name='student-today-lessons'),
    path('student/lessons/upcoming/', StudentUpcomingLessonsView.as_view(), name='student-upcoming-lessons'),
    path('student/attendance/', StudentAttendanceView.as_view(), name='student-attendance'),
    path('student/payments/', StudentPaymentsView.as_view(), name='student-payments'),
    path('student/leaderboard/', StudentLeaderboardView.as_view(), name='student-leaderboard'),
    path('student/stats/', StudentStatsView.as_view(), name='student-stats'),
]

from django.urls import path
from .views import (
    HealthCheckView, ChatView, UploadView, DiagnosisView,
    BookingListView, BookingDetailView, ConversationListView, ConversationDetailView
)

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='api-health'),
    path('chat/', ChatView.as_view(), name='api-chat'),
    path('upload/', UploadView.as_view(), name='api-upload'),
    path('diagnosis/', DiagnosisView.as_view(), name='api-diagnosis'),
    path('booking/', BookingListView.as_view(), name='api-booking-list-create'),
    path('booking/<str:pk>/', BookingDetailView.as_view(), name='api-booking-detail'),
    path('conversation/', ConversationListView.as_view(), name='api-conversation-list'),
    path('conversation/<str:pk>/', ConversationDetailView.as_view(), name='api-conversation-detail'),
]


from django.urls import path
from .views import (
    HealthCheckView, ChatView, UploadView, DiagnosisView, BookingView, ConversationDetailView
)

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='api-health'),
    path('chat/', ChatView.as_view(), name='api-chat'),
    path('upload/', UploadView.as_view(), name='api-upload'),
    path('diagnosis/', DiagnosisView.as_view(), name='api-diagnosis'),
    path('booking/', BookingView.as_view(), name='api-booking-create'),
    path('booking/<str:pk>/', BookingView.as_view(), name='api-booking-detail'),
    path('conversation/', ConversationDetailView.as_view(), name='api-conversation-list'),
    path('conversation/<str:pk>/', ConversationDetailView.as_view(), name='api-conversation-detail'),
]

from django.urls import path
from .views import (
    ChatView, UploadView, DiagnosisView, BookingView, ConversationDetailView
)

urlpatterns = [
    path('chat/', ChatView.as_view(), name='api-chat'),
    path('upload/', UploadView.as_view(), name='api-upload'),
    path('diagnosis/', DiagnosisView.as_view(), name='api-diagnosis'),
    path('booking/', BookingView.as_view(), name='api-booking-create'),
    path('booking/<uuid:pk>/', BookingView.as_view(), name='api-booking-detail'),
    path('conversation/<uuid:pk>/', ConversationDetailView.as_view(), name='api-conversation-detail'),
]

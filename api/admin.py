from django.contrib import admin
from .models import Conversation, Message, MediaAttachment, Diagnosis, Booking

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'car_make', 'car_model', 'car_year', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('car_make', 'car_model', 'id')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'is_ai_generated', 'created_at')
    list_filter = ('sender', 'is_ai_generated', 'created_at')
    search_fields = ('content',)

@admin.register(MediaAttachment)
class MediaAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'file_type', 'original_name', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at')

@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ('id', 'issue_title', 'severity', 'recommended_service', 'created_at')
    list_filter = ('severity', 'created_at')
    search_fields = ('issue_title', 'recommended_service')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'customer_email', 'customer_phone', 'status', 'preferred_date', 'created_at')
    list_filter = ('status', 'preferred_date')
    search_fields = ('customer_name', 'customer_email', 'customer_phone')

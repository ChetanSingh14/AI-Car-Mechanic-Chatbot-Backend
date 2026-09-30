from rest_framework import serializers
from .models import Conversation, Message, MediaAttachment, Diagnosis, Booking

class MediaAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = MediaAttachment
        fields = ['id', 'conversation', 'file', 'file_url', 'file_type', 'original_name', 'analysis_summary', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at', 'analysis_summary']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            if request is not None:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'content', 'is_ai_generated', 'created_at']
        read_only_fields = ['id', 'created_at']


class DiagnosisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diagnosis
        fields = ['id', 'conversation', 'issue_title', 'severity', 'description', 'recommended_service', 'estimated_cost', 'created_at']
        read_only_fields = ['id', 'created_at']


class BookingSerializer(serializers.ModelSerializer):
    diagnosis = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    diagnosis_detail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Booking
        fields = ['id', 'diagnosis', 'diagnosis_detail', 'customer_name', 'customer_email', 'customer_phone', 'preferred_date', 'preferred_time', 'notes', 'status', 'created_at']
        read_only_fields = ['id', 'created_at', 'status']

    def get_diagnosis_detail(self, obj):
        if hasattr(obj, 'diagnosis') and obj.diagnosis:
            return DiagnosisSerializer(obj.diagnosis).data
        return None

    def validate_customer_phone(self, value):
        cleaned = ''.join(c for c in value if c.isdigit() or c in ['+', '-', ' ', '(', ')'])
        if len(cleaned) < 7:
            raise serializers.ValidationError("Please provide a valid phone number with at least 7 digits.")
        return value


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    media_attachments = MediaAttachmentSerializer(many=True, read_only=True)
    diagnosis = DiagnosisSerializer(read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'car_make', 'car_model', 'car_year', 'symptom_category', 'status', 'messages', 'media_attachments', 'diagnosis', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatRequestSerializer(serializers.Serializer):
    conversation_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    message = serializers.CharField(required=True, allow_blank=False, max_length=2000)
    car_make = serializers.CharField(required=False, allow_blank=True, max_length=50)
    car_model = serializers.CharField(required=False, allow_blank=True, max_length=50)
    car_year = serializers.CharField(required=False, allow_blank=True, max_length=10)
    media_attachment_ids = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )


class MediaUploadSerializer(serializers.Serializer):
    conversation_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    file = serializers.FileField(required=True)

    def validate_file(self, value):
        max_size = 50 * 1024 * 1024  # 50MB max limit
        if value.size > max_size:
            raise serializers.ValidationError("File size exceeds maximum limit of 50MB.")
        return value


class DiagnosisRequestSerializer(serializers.Serializer):
    conversation_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

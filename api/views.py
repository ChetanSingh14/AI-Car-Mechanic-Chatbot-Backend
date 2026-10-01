import uuid
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Conversation, Message, MediaAttachment, Diagnosis, Booking
from .serializers import (
    ConversationSerializer, MessageSerializer, MediaAttachmentSerializer,
    DiagnosisSerializer, BookingSerializer, ChatRequestSerializer,
    MediaUploadSerializer, DiagnosisRequestSerializer
)
from .services import IntentService, GeminiMechanicService, BookingService


def resolve_conversation(conversation_id_str):
    """
    Validates and resolves a conversation ID.
    Returns: (conversation_object, error_response_or_None)
    """
    if not conversation_id_str:
        return None, None
    try:
        val_uuid = uuid.UUID(str(conversation_id_str).strip())
        conv = Conversation.objects.filter(id=val_uuid).first()
        if conv:
            return conv, None
        return None, Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": f"Conversation {conversation_id_str} not found."}},
            status=status.HTTP_404_NOT_FOUND
        )
    except (ValueError, TypeError, AttributeError):
        return None, Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": f"Invalid conversation ID format: {conversation_id_str}"}},
            status=status.HTTP_404_NOT_FOUND
        )


class HealthCheckView(APIView):
    """
    GET /api/health/
    Lightweight health check endpoint for uptime monitoring and frontend connectivity verification.
    """
    @extend_schema(
        responses={200: OpenApiResponse(description="Health status")}
    )
    def get(self, request):
        return Response({
            "status": "healthy",
            "service": "ai-car-mechanic-backend",
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_200_OK)


class ChatView(APIView):
    """
    POST /api/chat/
    Send a message to the AI Automobile Technician chatbot.
    Minimizes AI API usage by utilizing traditional rule-based intent classification.
    """
    @extend_schema(
        request=ChatRequestSerializer,
        responses={200: OpenApiResponse(description="Chat response from mechanic assistant")}
    )
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        conv_id_str = data.get('conversation_id')
        user_text = data['message'].strip()

        # If a conversation_id was provided, it MUST exist in the DB
        if conv_id_str:
            conversation, err = resolve_conversation(conv_id_str)
            if err:
                return err
        else:
            # Otherwise, start a new conversation
            conversation = Conversation.objects.create(
                car_make=data.get('car_make', ''),
                car_model=data.get('car_model', ''),
                car_year=data.get('car_year', '')
            )

        # Update vehicle info if provided in request
        if data.get('car_make'):
            conversation.car_make = data['car_make']
        if data.get('car_model'):
            conversation.car_model = data['car_model']
        if data.get('car_year'):
            conversation.car_year = data['car_year']

        # Save user message
        user_message = Message.objects.create(
            conversation=conversation,
            sender='user',
            content=user_text,
            is_ai_generated=False
        )

        # Link any provided media attachment IDs to this user message and conversation
        media_attachment_ids = data.get('media_attachment_ids') or []
        for m_id in media_attachment_ids:
            try:
                m_uuid = uuid.UUID(str(m_id))
                MediaAttachment.objects.filter(id=m_uuid).update(
                    conversation=conversation,
                    message=user_message
                )
            except (ValueError, TypeError):
                pass

        # Step 1: Traditional Rule-Based Intent Evaluation (Minimizes AI Usage!)
        intent_result = IntentService.evaluate_intent(user_text, conversation)

        if intent_result['extracted_info'].get('car_make') and not conversation.car_make:
            conversation.car_make = intent_result['extracted_info']['car_make']
        if intent_result['extracted_info'].get('symptom_category') and not conversation.symptom_category:
            conversation.symptom_category = intent_result['extracted_info']['symptom_category']
        
        conversation.save()

        if intent_result['action'] in ['REJECT', 'FOLLOWUP']:
            assistant_response_text = intent_result['response_text']
            is_ai = False
        else:
            # Step 2: Use Gemini AI or Fallback Senior Technician Engine
            media_list = conversation.media_attachments.all()
            ai_res = GeminiMechanicService.generate_chat_response(conversation, user_text, media_attachments=media_list)
            assistant_response_text = ai_res['text']
            is_ai = ai_res['is_ai_generated']

        # Save assistant response message
        assistant_message = Message.objects.create(
            conversation=conversation,
            sender='assistant',
            content=assistant_response_text,
            is_ai_generated=is_ai
        )

        return Response({
            "success": True,
            "data": {
                "conversation_id": str(conversation.id),
                "car_make": conversation.car_make,
                "car_model": conversation.car_model,
                "car_year": conversation.car_year,
                "status": conversation.status,
                "user_message": MessageSerializer(user_message, context={'request': request}).data,
                "assistant_message": MessageSerializer(assistant_message, context={'request': request}).data,
                "is_ai_generated": is_ai
            }
        }, status=status.HTTP_200_OK)


class UploadView(APIView):
    """
    POST /api/upload/
    Upload media files (Image, Audio, Video) for diagnostic analysis.
    """
    @extend_schema(
        request=MediaUploadSerializer,
        responses={201: MediaAttachmentSerializer}
    )
    def post(self, request):
        serializer = MediaUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        conv_id_str = data.get('conversation_id')
        if conv_id_str:
            conversation, err = resolve_conversation(conv_id_str)
            if err:
                return err
        else:
            conversation = Conversation.objects.create()

        uploaded_file = data['file']
        content_type = uploaded_file.content_type.lower() if uploaded_file.content_type else ''
        file_name = uploaded_file.name.lower()

        if content_type.startswith('image/') or file_name.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
            file_type = 'image'
        elif content_type.startswith('audio/') or file_name.endswith(('.mp3', '.wav', '.m4a', '.ogg', '.aac', '.webm')):
            file_type = 'audio'
        elif content_type.startswith('video/') or file_name.endswith(('.mp4', '.mov', '.avi', '.webm', '.mkv')):
            file_type = 'video'
        else:
            file_type = 'other'

        media = MediaAttachment.objects.create(
            conversation=conversation,
            file=uploaded_file,
            file_type=file_type,
            original_name=uploaded_file.name,
            analysis_summary=f"Uploaded {file_type.upper()}: {uploaded_file.name}"
        )

        # Single-pass media analysis (cached so files aren't re-uploaded every turn)
        GeminiMechanicService.analyze_media_file_once(media)

        # Also register a system note in chat history
        Message.objects.create(
            conversation=conversation,
            sender='system',
            content=f"📎 [Uploaded {file_type.upper()}: {uploaded_file.name}]"
        )

        return Response({
            "success": True,
            "data": MediaAttachmentSerializer(media, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)


class DiagnosisView(APIView):
    """
    POST /api/diagnosis/
    Generate official diagnosis, repair recommendations, and estimated costs.
    """
    @extend_schema(
        request=DiagnosisRequestSerializer,
        responses={200: DiagnosisSerializer}
    )
    def post(self, request):
        serializer = DiagnosisRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conv_id = serializer.validated_data.get('conversation_id')

        try:
            conversation = Conversation.objects.get(id=conv_id)
        except Conversation.DoesNotExist:
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": f"Conversation {conv_id} not found."}},
                status=status.HTTP_404_NOT_FOUND
            )

        # Caching check: if diagnosis already exists and no new user messages were added after it
        existing_diag = Diagnosis.objects.filter(conversation=conversation).first()
        if existing_diag:
            newer_messages = conversation.messages.filter(created_at__gt=existing_diag.created_at, sender='user')
            if not newer_messages.exists():
                return Response({
                    "success": True,
                    "data": DiagnosisSerializer(existing_diag).data
                }, status=status.HTTP_200_OK)

        diag_data, is_ai = GeminiMechanicService.generate_diagnosis(conversation)

        diagnosis, created = Diagnosis.objects.update_or_create(
            conversation=conversation,
            defaults={
                "issue_title": diag_data.get('issue_title', 'Vehicle Mechanical Issue'),
                "severity": diag_data.get('severity', 'medium'),
                "description": diag_data.get('description', 'Diagnostic analysis completed.'),
                "recommended_service": diag_data.get('recommended_service', 'General Mechanic Service'),
                "estimated_cost": diag_data.get('estimated_cost', '$150 - $350')
            }
        )

        conversation.status = 'diagnosed'
        conversation.save()

        # Add assistant message announcing diagnosis with accurate is_ai flag
        Message.objects.create(
            conversation=conversation,
            sender='assistant',
            content=(
                f"🔧 **Official Mechanic Diagnosis Summary**\n"
                f"**Issue:** {diagnosis.issue_title}\n"
                f"**Severity:** {diagnosis.severity.upper()}\n"
                f"**Recommended Repair:** {diagnosis.recommended_service}\n"
                f"**Estimated Cost:** {diagnosis.estimated_cost}\n\n"
                f"You can now click the **'Book Mechanic'** button to schedule an appointment with our certified technician team."
            ),
            is_ai_generated=is_ai
        )

        return Response({
            "success": True,
            "data": DiagnosisSerializer(diagnosis).data
        }, status=status.HTTP_200_OK)


class BookingView(APIView):
    """
    POST /api/booking/ - Create a new mechanic booking appointment.
    GET /api/booking/{id}/ - Retrieve details of a booking appointment.
    GET /api/booking/?email=... - List bookings for a given email.
    """
    @extend_schema(
        request=BookingSerializer,
        responses={201: BookingSerializer}
    )
    def post(self, request):
        serializer = BookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        diag_id = data.get('diagnosis')
        diag_obj = Diagnosis.objects.filter(id=diag_id).first()
        if not diag_obj:
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": f"Diagnosis {diag_id} not found."}},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            booking = BookingService.create_booking(
                diagnosis_id=diag_obj.id,
                customer_name=data['customer_name'],
                customer_email=data['customer_email'],
                customer_phone=data['customer_phone'],
                preferred_date=data['preferred_date'],
                preferred_time=data['preferred_time'],
                notes=data.get('notes', ''),
                mechanic_name=data.get('mechanic_name', '')
            )
            return Response({
                "success": True,
                "data": BookingSerializer(booking).data
            }, status=status.HTTP_201_CREATED)
        except ValueError as ve:
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(ve)}},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        responses={200: BookingSerializer}
    )
    def get(self, request, pk=None):
        if pk is not None:
            booking = BookingService.get_booking_details(pk)
            if not booking:
                return Response(
                    {"success": False, "error": {"code": "NOT_FOUND", "message": f"Booking {pk} not found."}},
                    status=status.HTTP_404_NOT_FOUND
                )
            return Response({
                "success": True,
                "data": BookingSerializer(booking).data
            }, status=status.HTTP_200_OK)

        email = request.query_params.get('email')
        if email:
            bookings = Booking.objects.filter(customer_email__iexact=email.strip())
            return Response({
                "success": True,
                "data": BookingSerializer(bookings, many=True).data
            }, status=status.HTTP_200_OK)

        return Response({
            "success": True,
            "data": BookingSerializer(Booking.objects.all()[:50], many=True).data
        }, status=status.HTTP_200_OK)


class ConversationDetailView(APIView):
    """
    GET /api/conversation/{id}/
    Retrieve conversation metadata, message history, media attachments, and diagnosis.
    GET /api/conversation/
    List recent conversations from DB.
    DELETE /api/conversation/{id}/
    Delete a conversation from DB.
    """
    def get(self, request, pk=None):
        if pk is None:
            conversations = Conversation.objects.prefetch_related('messages', 'media_attachments').all()[:50]
            return Response({
                "success": True,
                "data": ConversationSerializer(conversations, many=True, context={'request': request}).data
            }, status=status.HTTP_200_OK)

        try:
            val_uuid = uuid.UUID(str(pk))
            conversation = Conversation.objects.prefetch_related('messages', 'media_attachments').get(id=val_uuid)
        except (ValueError, TypeError, Conversation.DoesNotExist):
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": f"Conversation {pk} not found."}},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({
            "success": True,
            "data": ConversationSerializer(conversation, context={'request': request}).data
        }, status=status.HTTP_200_OK)

    def delete(self, request, pk=None):
        if pk is None:
            return Response(
                {"success": False, "error": {"code": "BAD_REQUEST", "message": "Conversation ID is required."}},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            val_uuid = uuid.UUID(str(pk))
            conv = Conversation.objects.get(id=val_uuid)
            conv.delete()
            return Response({
                "success": True,
                "data": {"id": str(val_uuid), "deleted": True}
            }, status=status.HTTP_200_OK)
        except (ValueError, TypeError, Conversation.DoesNotExist):
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": f"Conversation {pk} not found."}},
                status=status.HTTP_404_NOT_FOUND
            )

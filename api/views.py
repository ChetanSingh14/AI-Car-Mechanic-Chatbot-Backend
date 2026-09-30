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

        conversation_id = data.get('conversation_id')
        user_text = data['message'].strip()

        # Get or create conversation
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                return Response(
                    {"success": False, "error": {"code": "NOT_FOUND", "message": f"Conversation {conversation_id} not found."}},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
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
        conversation.save()

        # Save user message
        user_message = Message.objects.create(
            conversation=conversation,
            sender='user',
            content=user_text
        )

        # Step 1: Traditional Rule-Based Intent Evaluation (Minimizes AI Usage!)
        intent_result = IntentService.evaluate_intent(user_text, conversation)

        if intent_result['extracted_info'].get('car_make') and not conversation.car_make:
            conversation.car_make = intent_result['extracted_info']['car_make']
            conversation.save()

        if intent_result['action'] in ['REJECT', 'FOLLOWUP']:
            assistant_response_text = intent_result['response_text']
            is_ai = False
        else:
            # Step 2: Use Gemini API or Expert Mechanic Engine
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
                "user_message": MessageSerializer(user_message).data,
                "assistant_message": MessageSerializer(assistant_message).data,
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

        try:
            conversation = Conversation.objects.get(id=data['conversation_id'])
        except Conversation.DoesNotExist:
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": "Conversation not found."}},
                status=status.HTTP_404_NOT_FOUND
            )

        uploaded_file = data['file']
        content_type = uploaded_file.content_type.lower() if uploaded_file.content_type else ''
        file_name = uploaded_file.name.lower()

        if content_type.startswith('image/') or file_name.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            file_type = 'image'
        elif content_type.startswith('audio/') or file_name.endswith(('.mp3', '.wav', '.m4a', '.ogg')):
            file_type = 'audio'
        elif content_type.startswith('video/') or file_name.endswith(('.mp4', '.mov', '.avi', '.webm')):
            file_type = 'video'
        else:
            file_type = 'other'

        media = MediaAttachment.objects.create(
            conversation=conversation,
            file=uploaded_file,
            file_type=file_type,
            original_name=uploaded_file.name,
            analysis_summary=f"Uploaded {file_type.upper()} file ready for diagnostic evaluation."
        )

        # Also register a system/user note in chat history
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
        conv_id = serializer.validated_data['conversation_id']

        try:
            conversation = Conversation.objects.get(id=conv_id)
        except Conversation.DoesNotExist:
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": "Conversation not found."}},
                status=status.HTTP_404_NOT_FOUND
            )

        diag_data = GeminiMechanicService.generate_diagnosis(conversation)

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

        # Add assistant message announcing diagnosis
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
            is_ai_generated=False
        )

        return Response({
            "success": True,
            "data": DiagnosisSerializer(diagnosis).data
        }, status=status.HTTP_200_OK)


class BookingView(APIView):
    """
    POST /api/booking/ - Create a new mechanic booking appointment.
    GET /api/booking/{id}/ - Retrieve details of a booking appointment.
    """
    @extend_schema(
        request=BookingSerializer,
        responses={201: BookingSerializer}
    )
    def post(self, request):
        serializer = BookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            booking = BookingService.create_booking(
                diagnosis_id=data['diagnosis'].id,
                customer_name=data['customer_name'],
                customer_email=data['customer_email'],
                customer_phone=data['customer_phone'],
                preferred_date=data['preferred_date'],
                preferred_time=data['preferred_time'],
                notes=data.get('notes', '')
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


class ConversationDetailView(APIView):
    """
    GET /api/conversation/{id}/
    Retrieve conversation metadata, message history, media attachments, and diagnosis.
    """
    def get(self, request, pk=None):
        try:
            conversation = Conversation.objects.prefetch_related('messages', 'media_attachments').get(id=pk)
        except Conversation.DoesNotExist:
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": f"Conversation {pk} not found."}},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response({
            "success": True,
            "data": ConversationSerializer(conversation, context={'request': request}).data
        }, status=status.HTTP_200_OK)

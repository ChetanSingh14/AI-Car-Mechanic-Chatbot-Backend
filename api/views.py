import uuid
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import (
    extend_schema, OpenApiResponse, OpenApiParameter, OpenApiExample, inline_serializer
)

from .models import Conversation, Message, MediaAttachment, Diagnosis, Booking
from .serializers import (
    ConversationSerializer, MessageSerializer, MediaAttachmentSerializer,
    DiagnosisSerializer, BookingSerializer, ChatRequestSerializer,
    MediaUploadSerializer, DiagnosisRequestSerializer
)
from .services import IntentService, GeminiMechanicService, BookingService


def get_client_token(request):
    """
    Extracts the anonymous browser client token from X-Client-Token header.
    """
    header_val = request.headers.get('X-Client-Token', '') or request.META.get('HTTP_X_CLIENT_TOKEN', '')
    token = header_val.strip() if header_val else None
    return token if token else None


def resolve_conversation(conversation_id_str, client_token=None):
    """
    Validates and resolves a conversation ID, enforcing privacy isolation when client_token is present.
    Returns: (conversation_object, error_response_or_None)
    """
    if not conversation_id_str:
        return None, None
    try:
        val_uuid = uuid.UUID(str(conversation_id_str).strip())
        conv = Conversation.objects.filter(id=val_uuid).first()
        if not conv:
            return None, Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": f"Conversation {conversation_id_str} not found."}},
                status=status.HTTP_404_NOT_FOUND
            )
        # Privacy isolation: if conversation has a token, verify matching client_token is provided
        if conv.client_token and conv.client_token != client_token:
            return None, Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": f"Conversation {conversation_id_str} not found."}},
                status=status.HTTP_404_NOT_FOUND
            )
        return conv, None
    except (ValueError, TypeError, AttributeError):
        return None, Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": f"Invalid conversation ID format: {conversation_id_str}"}},
            status=status.HTTP_404_NOT_FOUND
        )


CLIENT_TOKEN_HEADER_PARAM = OpenApiParameter(
    name='X-Client-Token',
    type=str,
    location=OpenApiParameter.HEADER,
    description='Anonymous client token stored in browser localStorage for user privacy & session isolation.',
    required=False
)


class HealthCheckView(APIView):
    """
    GET /api/health/
    Lightweight health check endpoint for uptime monitoring and frontend connectivity verification.
    """
    @extend_schema(
        operation_id="health_check",
        summary="Service Health Check",
        description="Returns service health status and current UTC server timestamp.",
        responses={
            200: OpenApiResponse(
                description="Backend service is operational",
                examples=[
                    OpenApiExample(
                        "Healthy Response",
                        value={"status": "healthy", "service": "ai-car-mechanic-backend", "timestamp": "2026-10-01T12:00:00.000Z"}
                    )
                ]
            )
        }
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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'chat'
    @extend_schema(
        operation_id="chat_send_message",
        summary="Send Diagnostic Chat Message",
        description="Process a user vehicle inquiry. Routes through traditional zero-token intent filter first, then Gemini AI when appropriate.",
        parameters=[CLIENT_TOKEN_HEADER_PARAM],
        request=ChatRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="Chat response from mechanic technician assistant",
                examples=[
                    OpenApiExample(
                        "Successful Diagnostic Reply",
                        value={
                            "success": True,
                            "data": {
                                "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "car_make": "Honda",
                                "car_model": "Civic",
                                "car_year": "2019",
                                "status": "active",
                                "user_message": {
                                    "id": "e7b0c8b2-5f64-4e2b-8a7e-1a2b3c4d5e6f",
                                    "conversation": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                    "sender": "user",
                                    "content": "My brakes are squealing when stopping.",
                                    "is_ai_generated": False,
                                    "created_at": "2026-10-01T12:00:00.000Z",
                                    "media_attachments": []
                                },
                                "assistant_message": {
                                    "id": "f8c1d9a3-6e75-4f3c-9b8f-2b3c4d5e6f7a",
                                    "conversation": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                    "sender": "assistant",
                                    "content": "Squealing during braking indicates brake pad friction wear...",
                                    "is_ai_generated": True,
                                    "created_at": "2026-10-01T12:00:02.000Z",
                                    "media_attachments": []
                                },
                                "is_ai_generated": True
                            }
                        }
                    ),
                    OpenApiExample(
                        "Off-Topic Rejection (0 AI Tokens)",
                        value={
                            "success": True,
                            "data": {
                                "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "car_make": None,
                                "car_model": None,
                                "car_year": None,
                                "status": "active",
                                "user_message": {
                                    "id": "e7b0c8b2-5f64-4e2b-8a7e-1a2b3c4d5e6f",
                                    "conversation": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                    "sender": "user",
                                    "content": "Give me a cookie recipe",
                                    "is_ai_generated": False,
                                    "created_at": "2026-10-01T12:00:00.000Z",
                                    "media_attachments": []
                                },
                                "assistant_message": {
                                    "id": "f8c1d9a3-6e75-4f3c-9b8f-2b3c4d5e6f7a",
                                    "conversation": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                    "sender": "assistant",
                                    "content": "I am a specialized Automobile Technician AI. I can only assist with vehicle troubleshooting...",
                                    "is_ai_generated": False,
                                    "created_at": "2026-10-01T12:00:01.000Z",
                                    "media_attachments": []
                                },
                                "is_ai_generated": False
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Validation Error",
                examples=[
                    OpenApiExample(
                        "Blank Message Error",
                        value={"success": False, "error": {"code": "VALIDATION_ERROR", "message": "message: This field may not be blank."}}
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Conversation Not Found",
                examples=[
                    OpenApiExample(
                        "Not Found Error",
                        value={"success": False, "error": {"code": "NOT_FOUND", "message": "Conversation 00000000-0000-0000-0000-000000000000 not found."}}
                    )
                ]
            )
        }
    )
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        client_token = get_client_token(request)
        conv_id_str = data.get('conversation_id')
        user_text = data['message'].strip()

        # If a conversation_id was provided, it MUST exist in the DB and match client_token
        if conv_id_str:
            conversation, err = resolve_conversation(conv_id_str, client_token=client_token)
            if err:
                return err
            # If conversation has no client_token yet, associate it
            if not conversation.client_token and client_token:
                conversation.client_token = client_token
        else:
            # Otherwise, start a new conversation with client_token
            conversation = Conversation.objects.create(
                client_token=client_token,
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

        # Privacy security: ONLY link media attachments that belong to THIS same conversation
        media_attachment_ids = data.get('media_attachment_ids') or []
        for m_id in media_attachment_ids:
            try:
                m_uuid = uuid.UUID(str(m_id))
                MediaAttachment.objects.filter(id=m_uuid, conversation=conversation).update(
                    message=user_message
                )
            except (ValueError, TypeError):
                pass

        # Step 1: Traditional Rule-Based Intent Evaluation (Minimizes AI Usage!)
        intent_result = IntentService.evaluate_intent(user_text, conversation)

        if intent_result['extracted_info'].get('car_make') and not conversation.car_make:
            conversation.car_make = intent_result['extracted_info']['car_make']

        # Bug fix: allow updating symptom_category if it was empty or general
        symptom_cat = intent_result['extracted_info'].get('symptom_category')
        if symptom_cat and (not conversation.symptom_category or conversation.symptom_category == 'general'):
            conversation.symptom_category = symptom_cat

        conversation.save()

        if intent_result['action'] in ['REJECT', 'FOLLOWUP', 'OBD_LOOKUP']:
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
    Upload media files (Image, Audio, Video, Max 4 MB) for diagnostic analysis.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'upload'
    @extend_schema(
        operation_id="upload_media_file",
        summary="Upload Diagnostic Media (Max 4 MB)",
        description="Upload an image, audio clip, or video file for acoustic/visual inspection. Analyzed once and cached.",
        parameters=[CLIENT_TOKEN_HEADER_PARAM],
        request=MediaUploadSerializer,
        responses={
            201: OpenApiResponse(
                response=MediaAttachmentSerializer,
                description="Media uploaded and queued for inspection",
                examples=[
                    OpenApiExample(
                        "Uploaded Media Response",
                        value={
                            "success": True,
                            "data": {
                                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "conversation": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "file_url": "http://13.234.4.236/media/uploads/2026/10/01/sample.png",
                                "file_type": "image",
                                "original_name": "brake_pad.png",
                                "analysis_summary": None,
                                "uploaded_at": "2026-10-01T12:00:00.000Z"
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="File validation error or size exceeds 4MB",
                examples=[
                    OpenApiExample(
                        "File Too Large",
                        value={"success": False, "error": {"code": "VALIDATION_ERROR", "message": "file: File size exceeds maximum limit of 4MB."}}
                    )
                ]
            ),
            404: OpenApiResponse(description="Conversation not found")
        }
    )
    def post(self, request):
        serializer = MediaUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        client_token = get_client_token(request)
        conv_id_str = data.get('conversation_id')
        if conv_id_str:
            conversation, err = resolve_conversation(conv_id_str, client_token=client_token)
            if err:
                return err
            if not conversation.client_token and client_token:
                conversation.client_token = client_token
                conversation.save(update_fields=['client_token'])
        else:
            conversation = Conversation.objects.create(client_token=client_token)

        uploaded_file = data['file']
        content_type = uploaded_file.content_type.lower() if uploaded_file.content_type else ''
        file_name = uploaded_file.name.lower()

        if content_type.startswith('image/') or file_name.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic')):
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
            analysis_summary=None
        )

        # Note: Media inspection is evaluated on-demand during chat/diagnosis to keep upload latency < 10ms
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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'diagnosis'
    @extend_schema(
        operation_id="diagnosis_generate",
        summary="Generate Formal Vehicle Diagnosis & Repair Estimate",
        description="Generates an itemized technical diagnostic assessment, severity score, and repair estimate. Reuses cached diagnosis if no new user messages have arrived.",
        parameters=[CLIENT_TOKEN_HEADER_PARAM],
        request=DiagnosisRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=DiagnosisSerializer,
                description="Diagnosis generated or returned from cache",
                examples=[
                    OpenApiExample(
                        "Certified Diagnosis Report",
                        value={
                            "success": True,
                            "data": {
                                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "conversation": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "issue_title": "Worn Front Brake Pads & Rotors",
                                "severity": "high",
                                "description": "Friction pad wear indicators have made contact with rotors, reducing stopping distance.",
                                "recommended_service": "Front Brake Pad & Rotor Replacement",
                                "estimated_cost": "$220 - $450",
                                "created_at": "2026-10-01T12:00:00.000Z",
                                "updated_at": "2026-10-01T12:00:00.000Z"
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Missing conversation ID",
                examples=[
                    OpenApiExample(
                        "Missing ID",
                        value={"success": False, "error": {"code": "VALIDATION_ERROR", "message": "conversation_id: This field is required."}}
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Conversation not found",
                examples=[
                    OpenApiExample(
                        "Not Found",
                        value={"success": False, "error": {"code": "NOT_FOUND", "message": "Conversation not found."}}
                    )
                ]
            )
        }
    )
    def post(self, request):
        serializer = DiagnosisRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conv_id = serializer.validated_data.get('conversation_id')

        client_token = get_client_token(request)
        conversation, err = resolve_conversation(conv_id, client_token=client_token)
        if err:
            return err

        # Caching check: if diagnosis already exists and no new user messages were added after its last update
        existing_diag = Diagnosis.objects.filter(conversation=conversation).first()
        if existing_diag:
            newer_messages = conversation.messages.filter(created_at__gt=existing_diag.updated_at, sender='user')
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


class BookingListView(APIView):
    """
    POST /api/booking/ - Create a new mechanic booking appointment.
    GET /api/booking/ - List bookings for the current client token (or query by email).
    """
    @extend_schema(
        operation_id="booking_create",
        summary="Create Mechanic Appointment Booking",
        description="Book a repair appointment tied to a valid diagnosis record.",
        parameters=[CLIENT_TOKEN_HEADER_PARAM],
        request=BookingSerializer,
        responses={
            201: OpenApiResponse(
                response=BookingSerializer,
                description="Booking confirmed",
                examples=[
                    OpenApiExample(
                        "Confirmed Booking",
                        value={
                            "success": True,
                            "data": {
                                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "diagnosis": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "mechanic_name": "Precision Master Automotive",
                                "customer_name": "John Doe",
                                "customer_email": "john@example.com",
                                "customer_phone": "+15551234567",
                                "preferred_date": "2026-10-15",
                                "preferred_time": "10:00 AM",
                                "notes": "Loaner car requested",
                                "status": "confirmed",
                                "created_at": "2026-10-01T12:00:00.000Z"
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Validation error (e.g. past appointment date or invalid phone)",
                examples=[
                    OpenApiExample(
                        "Past Date Error",
                        value={"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Appointment date cannot be in the past."}}
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Diagnosis not found",
                examples=[
                    OpenApiExample(
                        "Diagnosis Not Found",
                        value={"success": False, "error": {"code": "NOT_FOUND", "message": "Diagnosis 00000000-0000-0000-0000-000000000000 not found."}}
                    )
                ]
            )
        }
    )
    def post(self, request):
        serializer = BookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        client_token = get_client_token(request)
        diag_id = data.get('diagnosis')
        diag_obj = Diagnosis.objects.filter(id=diag_id).first()
        if not diag_obj:
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": f"Diagnosis {diag_id} not found."}},
                status=status.HTTP_404_NOT_FOUND
            )

        # Privacy check: if conversation has a client_token, verify match
        if diag_obj.conversation.client_token and diag_obj.conversation.client_token != client_token:
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
        operation_id="booking_list",
        summary="List User Bookings",
        description="List booking appointments for the current client token or filter by customer email.",
        parameters=[
            CLIENT_TOKEN_HEADER_PARAM,
            OpenApiParameter(name='email', type=str, location=OpenApiParameter.QUERY, description='Filter bookings by customer email address', required=False)
        ],
        responses={
            200: OpenApiResponse(
                response=BookingSerializer(many=True),
                description="List of bookings",
                examples=[
                    OpenApiExample(
                        "Booking List",
                        value={
                            "success": True,
                            "data": [
                                {
                                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                    "diagnosis": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                    "mechanic_name": "Precision Master Automotive",
                                    "customer_name": "John Doe",
                                    "customer_email": "john@example.com",
                                    "customer_phone": "+15551234567",
                                    "preferred_date": "2026-10-15",
                                    "preferred_time": "10:00 AM",
                                    "notes": "",
                                    "status": "confirmed",
                                    "created_at": "2026-10-01T12:00:00.000Z"
                                }
                            ]
                        }
                    )
                ]
            )
        }
    )
    def get(self, request):
        client_token = get_client_token(request)
        email = request.query_params.get('email')

        queryset = Booking.objects.all()

        # Privacy isolation: require client_token to list bookings
        if not client_token:
            return Response({"success": True, "data": []}, status=status.HTTP_200_OK)

        queryset = queryset.filter(diagnosis__conversation__client_token=client_token)

        if email:
            queryset = queryset.filter(customer_email__iexact=email.strip())

        return Response({
            "success": True,
            "data": BookingSerializer(queryset[:50], many=True).data
        }, status=status.HTTP_200_OK)


class BookingDetailView(APIView):
    """
    GET /api/booking/{id}/ - Retrieve details of a booking appointment.
    """
    @extend_schema(
        operation_id="booking_detail",
        summary="Retrieve Booking Details",
        description="Retrieve full details of a specific mechanic booking appointment.",
        parameters=[
            CLIENT_TOKEN_HEADER_PARAM,
            OpenApiParameter(name='pk', type=str, location=OpenApiParameter.PATH, description='Booking UUID', required=True)
        ],
        responses={
            200: OpenApiResponse(
                response=BookingSerializer,
                description="Booking record retrieved",
                examples=[
                    OpenApiExample(
                        "Booking Detail",
                        value={
                            "success": True,
                            "data": {
                                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "diagnosis": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "mechanic_name": "Precision Master Automotive",
                                "customer_name": "John Doe",
                                "customer_email": "john@example.com",
                                "customer_phone": "+15551234567",
                                "preferred_date": "2026-10-15",
                                "preferred_time": "10:00 AM",
                                "notes": "",
                                "status": "confirmed",
                                "created_at": "2026-10-01T12:00:00.000Z"
                            }
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Booking not found",
                examples=[
                    OpenApiExample(
                        "Not Found",
                        value={"success": False, "error": {"code": "NOT_FOUND", "message": "Booking 00000000-0000-0000-0000-000000000000 not found."}}
                    )
                ]
            )
        }
    )
    def get(self, request, pk=None):
        client_token = get_client_token(request)
        booking = BookingService.get_booking_details(pk)
        if not booking:
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": f"Booking {pk} not found."}},
                status=status.HTTP_404_NOT_FOUND
            )

        # Privacy check: if conversation has a client_token, verify match
        if booking.diagnosis.conversation.client_token and booking.diagnosis.conversation.client_token != client_token:
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": f"Booking {pk} not found."}},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({
            "success": True,
            "data": BookingSerializer(booking).data
        }, status=status.HTTP_200_OK)


class ConversationListView(APIView):
    """
    GET /api/conversation/ - List recent conversations for the current client token.
    """
    @extend_schema(
        operation_id="conversation_list",
        summary="List User Conversations",
        description="Retrieve history of diagnostic conversation sessions for the active browser client token.",
        parameters=[CLIENT_TOKEN_HEADER_PARAM],
        responses={
            200: OpenApiResponse(
                response=ConversationSerializer(many=True),
                description="List of conversation sessions",
                examples=[
                    OpenApiExample(
                        "Conversation List",
                        value={
                            "success": True,
                            "data": [
                                {
                                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                    "car_make": "Honda",
                                    "car_model": "Civic",
                                    "car_year": "2019",
                                    "symptom_category": "brakes",
                                    "status": "active",
                                    "messages": [],
                                    "media_attachments": [],
                                    "diagnosis": None,
                                    "created_at": "2026-10-01T12:00:00.000Z",
                                    "updated_at": "2026-10-01T12:00:00.000Z"
                                }
                            ]
                        }
                    )
                ]
            )
        }
    )
    def get(self, request):
        client_token = get_client_token(request)
        queryset = Conversation.objects.prefetch_related('messages', 'media_attachments')

        # Privacy isolation: filter by client token
        if client_token:
            queryset = queryset.filter(client_token=client_token)
        else:
            queryset = queryset.none()

        return Response({
            "success": True,
            "data": ConversationSerializer(queryset[:50], many=True, context={'request': request}).data
        }, status=status.HTTP_200_OK)


class ConversationDetailView(APIView):
    """
    GET /api/conversation/{id}/ - Retrieve full conversation metadata, message history, and diagnosis.
    DELETE /api/conversation/{id}/ - Delete a conversation session from DB.
    """
    @extend_schema(
        operation_id="conversation_detail",
        summary="Retrieve Conversation Session Detail",
        description="Retrieve complete conversation details, nested messages, attachments, and diagnosis record.",
        parameters=[
            CLIENT_TOKEN_HEADER_PARAM,
            OpenApiParameter(name='pk', type=str, location=OpenApiParameter.PATH, description='Conversation UUID', required=True)
        ],
        responses={
            200: OpenApiResponse(
                response=ConversationSerializer,
                description="Conversation details retrieved",
                examples=[
                    OpenApiExample(
                        "Conversation Detail",
                        value={
                            "success": True,
                            "data": {
                                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "car_make": "Honda",
                                "car_model": "Civic",
                                "car_year": "2019",
                                "symptom_category": "brakes",
                                "status": "active",
                                "messages": [],
                                "media_attachments": [],
                                "diagnosis": None,
                                "created_at": "2026-10-01T12:00:00.000Z",
                                "updated_at": "2026-10-01T12:00:00.000Z"
                            }
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Conversation not found",
                examples=[
                    OpenApiExample(
                        "Not Found",
                        value={"success": False, "error": {"code": "NOT_FOUND", "message": "Conversation 00000000-0000-0000-0000-000000000000 not found."}}
                    )
                ]
            )
        }
    )
    def get(self, request, pk=None):
        client_token = get_client_token(request)
        try:
            val_uuid = uuid.UUID(str(pk))
            conversation = Conversation.objects.prefetch_related('messages', 'media_attachments').get(id=val_uuid)
            if conversation.client_token and conversation.client_token != client_token:
                return Response(
                    {"success": False, "error": {"code": "NOT_FOUND", "message": f"Conversation {pk} not found."}},
                    status=status.HTTP_404_NOT_FOUND
                )
        except (ValueError, TypeError, Conversation.DoesNotExist):
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": f"Conversation {pk} not found."}},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({
            "success": True,
            "data": ConversationSerializer(conversation, context={'request': request}).data
        }, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="conversation_delete",
        summary="Delete Conversation Session",
        description="Permanently delete a conversation session and all associated messages, media, and diagnosis from the database.",
        parameters=[
            CLIENT_TOKEN_HEADER_PARAM,
            OpenApiParameter(name='pk', type=str, location=OpenApiParameter.PATH, description='Conversation UUID', required=True)
        ],
        responses={
            200: OpenApiResponse(
                description="Conversation deleted successfully",
                examples=[
                    OpenApiExample(
                        "Deleted Response",
                        value={"success": True, "data": {"id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "deleted": True}}
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Conversation not found",
                examples=[
                    OpenApiExample(
                        "Not Found",
                        value={"success": False, "error": {"code": "NOT_FOUND", "message": "Conversation 00000000-0000-0000-0000-000000000000 not found."}}
                    )
                ]
            )
        }
    )
    def delete(self, request, pk=None):
        if pk is None:
            return Response(
                {"success": False, "error": {"code": "BAD_REQUEST", "message": "Conversation ID is required."}},
                status=status.HTTP_400_BAD_REQUEST
            )
        client_token = get_client_token(request)
        try:
            val_uuid = uuid.UUID(str(pk))
            conv = Conversation.objects.get(id=val_uuid)
            if conv.client_token and conv.client_token != client_token:
                return Response(
                    {"success": False, "error": {"code": "NOT_FOUND", "message": f"Conversation {pk} not found."}},
                    status=status.HTTP_404_NOT_FOUND
                )
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

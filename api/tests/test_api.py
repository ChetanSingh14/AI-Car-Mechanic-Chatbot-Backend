import datetime
import uuid
from unittest.mock import patch
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from api.models import Conversation, Message, MediaAttachment, Diagnosis, Booking
from api.services import GeminiMechanicService

class CarMechanicAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_key_patcher = patch('api.services.gemini_service.GeminiMechanicService.get_api_key', return_value='')
        self.api_key_patcher.start()
        self.grok_key_patcher = patch('api.services.gemini_service.GeminiMechanicService.get_grok_api_key', return_value='')
        self.grok_key_patcher.start()

    def tearDown(self):
        self.api_key_patcher.stop()
        self.grok_key_patcher.stop()

    def test_health_check_endpoint(self):
        """Test GET /api/health/ returns 200 OK and healthy status."""
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data.get('status'), 'healthy')


    @patch('api.services.gemini_service.GeminiMechanicService.generate_chat_response')
    def test_chat_non_automotive_query_rejected_without_ai(self, mock_gemini):
        """Test off-topic question is politely rejected via traditional logic without AI tokens."""
        url = '/api/chat/'
        payload = {
            "message": "Give me a recipe for chocolate chip cookies"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertFalse(data['data']['is_ai_generated'])
        self.assertIn("specialized Automobile Technician", data['data']['assistant_message']['content'])
        mock_gemini.assert_not_called()

    def test_obd_code_treated_as_car_query(self):
        """Test OBD code (e.g. P0300) is recognized as automotive issue even without 'car' keyword."""
        url = '/api/chat/'
        payload = {
            "message": "What does code P0300 mean?"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['success'])
        # Should not be rejected as off-topic
        self.assertNotIn("I can only assist with vehicle troubleshooting", data['data']['assistant_message']['content'])

    def test_greeting_triggers_followup_without_ai(self):
        """Test simple greeting like 'hi' triggers friendly follow-up without invoking AI."""
        url = '/api/chat/'
        payload = {
            "message": "Hi"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertFalse(data['data']['is_ai_generated'])
        self.assertIn("Hello", data['data']['assistant_message']['content'])

    def test_multi_turn_chat_preserves_conversation_id_and_history(self):
        """Test multi-turn chat preserves conversation_id and builds history."""
        # Turn 1
        res1 = self.client.post('/api/chat/', {"message": "I have a 2019 Honda Civic with squeaking brakes"}, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        conv_id = res1.json()['data']['conversation_id']
        self.assertTrue(conv_id)

        # Turn 2 with existing conversation_id
        res2 = self.client.post('/api/chat/', {
            "conversation_id": conv_id,
            "message": "The squeak happens mainly when coming to a complete stop at low speed."
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.json()['data']['conversation_id'], conv_id)

        conv = Conversation.objects.get(id=uuid.UUID(conv_id))
        self.assertEqual(conv.messages.count(), 4)  # 2 user + 2 assistant messages

    def test_chat_with_unknown_conversation_id_returns_404(self):
        """Test sending chat with unknown conversation_id returns 404 instead of quietly starting fresh."""
        fake_uuid = str(uuid.uuid4())
        response = self.client.post('/api/chat/', {
            "conversation_id": fake_uuid,
            "message": "Hello mechanic"
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error']['code'], 'NOT_FOUND')

    def test_file_upload_and_linking(self):
        """Test uploading diagnostic media attachment and linking to conversation."""
        conv = Conversation.objects.create(car_make="Toyota", car_model="Camry", car_year="2020")
        image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4'
        uploaded_file = SimpleUploadedFile("brake_inspection.png", image_content, content_type="image/png")

        payload = {
            "conversation_id": str(conv.id),
            "file": uploaded_file
        }
        response = self.client.post('/api/upload/', payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['file_type'], 'image')
        self.assertTrue(conv.media_attachments.filter(id=data['data']['id']).exists())

    def test_upload_with_unknown_conversation_returns_404(self):
        """Test upload with invalid/unknown conversation returns 404."""
        fake_uuid = str(uuid.uuid4())
        image_content = b'fake-image-bytes'
        uploaded_file = SimpleUploadedFile("test.png", image_content, content_type="image/png")
        response = self.client.post('/api/upload/', {
            "conversation_id": fake_uuid,
            "file": uploaded_file
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_diagnosis_generation_and_caching(self):
        """Test diagnosis generation and subsequent cached responses."""
        conv = Conversation.objects.create(car_make="Ford", car_model="F-150", car_year="2019")
        Message.objects.create(conversation=conv, sender='user', content="The engine is overheating and leaking coolant")

        # First call: generates diagnosis
        url = '/api/diagnosis/'
        payload = {"conversation_id": str(conv.id)}
        response1 = self.client.post(url, payload, format='json')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        data1 = response1.json()
        self.assertTrue(data1['success'])
        self.assertIn('issue_title', data1['data'])
        self.assertEqual(Diagnosis.objects.count(), 1)
        diag_id = data1['data']['id']

        # Second call without new user messages: returns cached diagnosis
        response2 = self.client.post(url, payload, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        data2 = response2.json()
        self.assertEqual(data2['data']['id'], diag_id)
        self.assertEqual(Diagnosis.objects.count(), 1)

    def test_diagnosis_unknown_conversation_returns_404(self):
        """Test diagnosis with unknown conversation returns 404."""
        fake_uuid = str(uuid.uuid4())
        response = self.client.post('/api/diagnosis/', {"conversation_id": fake_uuid}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_diagnosis_missing_conversation_returns_400(self):
        """Test diagnosis with missing conversation_id returns 400."""
        response = self.client.post('/api/diagnosis/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_workflow_with_mechanic_choice(self):
        """Test mechanics booking creation with mechanic_name and retrieval."""
        conv = Conversation.objects.create(car_make="Ford", car_model="Mustang", car_year="2021")
        diag = Diagnosis.objects.create(
            conversation=conv,
            issue_title="Alternator Failure",
            severity="high",
            description="Alternator not charging battery",
            recommended_service="Alternator Replacement",
            estimated_cost="$250 - $400"
        )

        future_date = (timezone.now() + datetime.timedelta(days=2)).strftime('%Y-%m-%d')
        payload = {
            "diagnosis": str(diag.id),
            "customer_name": "John Doe",
            "customer_email": "johndoe@example.com",
            "customer_phone": "+15551234567",
            "preferred_date": future_date,
            "preferred_time": "10:00 AM",
            "notes": "Please provide loaner car if repair takes > 3 hours.",
            "mechanic_name": "Precision Master Automotive"
        }
        response = self.client.post('/api/booking/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['mechanic_name'], "Precision Master Automotive")
        booking_id = data['data']['id']

        # Get booking detail
        get_res = self.client.get(f'/api/booking/{booking_id}/')
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        get_data = get_res.json()
        self.assertEqual(get_data['data']['customer_name'], "John Doe")
        self.assertEqual(get_data['data']['mechanic_name'], "Precision Master Automotive")

    def test_booking_with_missing_or_invalid_diagnosis_returns_400_or_404(self):
        """Test booking fails when diagnosis is missing or non-existent."""
        future_date = (timezone.now() + datetime.timedelta(days=2)).strftime('%Y-%m-%d')
        
        # Missing diagnosis
        res_missing = self.client.post('/api/booking/', {
            "customer_name": "Jane",
            "customer_email": "jane@example.com",
            "customer_phone": "+15551234567",
            "preferred_date": future_date,
            "preferred_time": "10:00 AM"
        }, format='json')
        self.assertEqual(res_missing.status_code, status.HTTP_400_BAD_REQUEST)

        # Non-existent diagnosis
        res_unknown = self.client.post('/api/booking/', {
            "diagnosis": str(uuid.uuid4()),
            "customer_name": "Jane",
            "customer_email": "jane@example.com",
            "customer_phone": "+15551234567",
            "preferred_date": future_date,
            "preferred_time": "10:00 AM"
        }, format='json')
        self.assertEqual(res_unknown.status_code, status.HTTP_404_NOT_FOUND)

    def test_booking_with_past_date_returns_400(self):
        """Test booking with past date returns 400 validation error."""
        conv = Conversation.objects.create(car_make="BMW", car_model="330i", car_year="2020")
        diag = Diagnosis.objects.create(
            conversation=conv,
            issue_title="Oil Leak",
            severity="medium",
            description="Oil filter housing leak",
            recommended_service="Gasket Replacement",
            estimated_cost="$200"
        )
        past_date = (timezone.now() - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
        payload = {
            "diagnosis": str(diag.id),
            "customer_name": "Alice",
            "customer_email": "alice@example.com",
            "customer_phone": "+15551234567",
            "preferred_date": past_date,
            "preferred_time": "10:00 AM"
        }
        res = self.client.post('/api/booking/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_non_uuid_id_returns_json_404(self):
        """Test GET /api/booking/not-a-uuid/ returns JSON 404 format instead of HTML error."""
        res = self.client.get('/api/booking/not-a-uuid/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(res['Content-Type'], 'application/json')
        data = res.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error']['code'], 'NOT_FOUND')

    def test_conversation_list_and_detail(self):
        """Test listing conversations and retrieving conversation detail."""
        conv = Conversation.objects.create(car_make="Mazda", car_model="CX-5", car_year="2022", client_token="tok_list_detail")
        Message.objects.create(conversation=conv, sender='user', content="Strange humming sound")
        Message.objects.create(conversation=conv, sender='assistant', content="Could be wheel bearing")

        # List
        res_list = self.client.get('/api/conversation/', HTTP_X_CLIENT_TOKEN="tok_list_detail")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        data_list = res_list.json()
        self.assertTrue(data_list['success'])
        self.assertGreaterEqual(len(data_list['data']), 1)

        # Detail
        res_detail = self.client.get(f'/api/conversation/{conv.id}/', HTTP_X_CLIENT_TOKEN="tok_list_detail")
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        data_detail = res_detail.json()
        self.assertTrue(data_detail['success'])
        self.assertEqual(data_detail['data']['car_make'], "Mazda")
        self.assertEqual(len(data_detail['data']['messages']), 2)


    def test_conversation_delete(self):
        """Test deleting a conversation removes it and cascaded messages."""
        conv = Conversation.objects.create(car_make="Audi", car_model="A4", car_year="2021")
        conv_id = str(conv.id)

        res_del = self.client.delete(f'/api/conversation/{conv_id}/')
        self.assertEqual(res_del.status_code, status.HTTP_200_OK)
        data = res_del.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['data']['deleted'])
        self.assertFalse(Conversation.objects.filter(id=conv.id).exists())

    def test_booking_list_by_email(self):
        """Test querying bookings by customer email."""
        conv = Conversation.objects.create(car_make="Toyota", car_model="RAV4", car_year="2020", client_token="tok-123")
        diag = Diagnosis.objects.create(
            conversation=conv,
            issue_title="Brake Wear",
            severity="medium",
            description="Pads worn",
            recommended_service="Brake Service",
            estimated_cost="$200"
        )
        Booking.objects.create(
            diagnosis=diag,
            customer_name="Bob Smith",
            customer_email="bob@example.com",
            customer_phone="+15559876543",
            preferred_date=timezone.now().date() + datetime.timedelta(days=3),
            preferred_time="11:00 AM",
            mechanic_name="Metro Auto"
        )

        res = self.client.get('/api/booking/?email=bob@example.com', HTTP_X_CLIENT_TOKEN="tok-123")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['customer_name'], "Bob Smith")

    def test_privacy_client_token_isolation(self):
        """Test conversations and bookings belonging to token A cannot be accessed or deleted by token B."""
        # Create conversation with Token A
        res_a = self.client.post(
            '/api/chat/',
            {"message": "Honda Civic 2020 rattling noise"},
            format='json',
            HTTP_X_CLIENT_TOKEN="client_alpha_token"
        )
        self.assertEqual(res_a.status_code, status.HTTP_200_OK)
        conv_id_a = res_a.json()['data']['conversation_id']

        # Token A lists conversations -> sees conv_id_a
        list_a = self.client.get('/api/conversation/', HTTP_X_CLIENT_TOKEN="client_alpha_token")
        self.assertEqual(list_a.status_code, status.HTTP_200_OK)
        ids_a = [c['id'] for c in list_a.json()['data']]
        self.assertIn(conv_id_a, ids_a)

        # Token B lists conversations -> does NOT see conv_id_a
        list_b = self.client.get('/api/conversation/', HTTP_X_CLIENT_TOKEN="client_beta_token")
        self.assertEqual(list_b.status_code, status.HTTP_200_OK)
        ids_b = [c['id'] for c in list_b.json()['data']]
        self.assertNotIn(conv_id_a, ids_b)

        # Token B tries to get conv_id_a -> 404
        get_b = self.client.get(f'/api/conversation/{conv_id_a}/', HTTP_X_CLIENT_TOKEN="client_beta_token")
        self.assertEqual(get_b.status_code, status.HTTP_404_NOT_FOUND)

        # Token B tries to delete conv_id_a -> 404
        del_b = self.client.delete(f'/api/conversation/{conv_id_a}/', HTTP_X_CLIENT_TOKEN="client_beta_token")
        self.assertEqual(del_b.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Conversation.objects.filter(id=conv_id_a).exists())

    def test_cross_conversation_media_attachment_protection(self):
        """Test that media attachments from conversation A cannot be linked into conversation B."""
        conv_a = Conversation.objects.create(client_token="tok_a")
        conv_b = Conversation.objects.create(client_token="tok_b")

        image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4'
        media_a = MediaAttachment.objects.create(
            conversation=conv_a,
            file=SimpleUploadedFile("pad.png", image_content, content_type="image/png"),
            file_type="image",
            original_name="pad.png"
        )

        # Chat in conversation B passes media_a id
        res_b = self.client.post(
            '/api/chat/',
            {
                "conversation_id": str(conv_b.id),
                "message": "Is this bad?",
                "media_attachment_ids": [str(media_a.id)]
            },
            format='json',
            HTTP_X_CLIENT_TOKEN="tok_b"
        )
        self.assertEqual(res_b.status_code, status.HTTP_200_OK)

        # Verify media_a was NOT linked to conversation B's message
        media_a.refresh_from_db()
        self.assertEqual(media_a.conversation_id, conv_a.id)
        self.assertIsNone(media_a.message)

    def test_error_message_formatting_clean_string(self):
        """Test validation error produces 'message: This field may not be blank.' without ErrorDetail wrapper."""
        res = self.client.post('/api/chat/', {"message": "   "}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        data = res.json()
        self.assertFalse(data['success'])
        self.assertIn("message: This field may not be blank.", data['error']['message'])
        self.assertNotIn("ErrorDetail", data['error']['message'])

    def test_symptom_category_updates_from_general(self):
        """Test symptom_category transitions from general to specific when clear symptom keywords are provided."""
        conv = Conversation.objects.create(symptom_category="general")
        self.client.post('/api/chat/', {
            "conversation_id": str(conv.id),
            "message": "My brakes are squealing and grinding every time I stop."
        }, format='json')
        conv.refresh_from_db()
        self.assertEqual(conv.symptom_category, "brakes")

    def test_upload_file_exceeding_4mb_rejected(self):
        """Test uploading a file larger than 4 MB is rejected with 400 validation error."""
        large_content = b'0' * (5 * 1024 * 1024)  # 5 MB
        large_file = SimpleUploadedFile("big_video.mp4", large_content, content_type="video/mp4")
        res = self.client.post('/api/upload/', {"file": large_file}, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        data = res.json()
        self.assertFalse(data['success'])
        self.assertIn("File size exceeds maximum limit of 4MB", data['error']['message'])

    def test_privacy_no_token_rejected_on_token_owned_conversation(self):
        """Test that requests lacking X-Client-Token cannot read, chat into, or delete token-owned sessions."""
        conv = Conversation.objects.create(car_make="Subaru", car_model="Outback", client_token="token_alice_secured")
        Message.objects.create(conversation=conv, sender="user", content="Whining steering sound")

        # 1. No token reading detail -> 404
        res_get = self.client.get(f'/api/conversation/{conv.id}/')
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

        # 2. No token posting into chat -> 404
        res_post = self.client.post('/api/chat/', {
            "conversation_id": str(conv.id),
            "message": "It gets louder when turning wheel"
        }, format='json')
        self.assertEqual(res_post.status_code, status.HTTP_404_NOT_FOUND)

        # 3. No token attempting deletion -> 404
        res_del = self.client.delete(f'/api/conversation/{conv.id}/')
        self.assertEqual(res_del.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Conversation.objects.filter(id=conv.id).exists())

        # 4. Valid token succeeds
        res_valid = self.client.get(f'/api/conversation/{conv.id}/', HTTP_X_CLIENT_TOKEN="token_alice_secured")
        self.assertEqual(res_valid.status_code, status.HTTP_200_OK)

    def test_client_token_never_exposed_in_api_responses(self):
        """Test that client_token is omitted from ConversationSerializer output to prevent token leaks."""
        conv = Conversation.objects.create(car_make="Hyundai", car_model="Tucson", client_token="token_secret_12345")
        res = self.client.get(f'/api/conversation/{conv.id}/', HTTP_X_CLIENT_TOKEN="token_secret_12345")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()['data']
        self.assertNotIn('client_token', data)

    def test_booking_list_requires_client_token_to_prevent_data_harvesting(self):
        """Test that GET /api/booking/?email= without client token returns empty list instead of sensitive info."""
        conv = Conversation.objects.create(client_token="alice_token_private")
        diag = Diagnosis.objects.create(
            conversation=conv,
            issue_title="Starter Motor",
            severity="high",
            description="Starter click",
            recommended_service="Starter Replacement",
            estimated_cost="$300"
        )
        Booking.objects.create(
            diagnosis=diag,
            customer_name="Alice Wonderland",
            customer_email="alice@wonderland.test",
            customer_phone="+15550001111",
            preferred_date=timezone.now().date() + datetime.timedelta(days=5),
            preferred_time="09:00 AM"
        )

        # Request with NO token must return empty list (prevents leaking name/phone)
        res_unauthenticated = self.client.get('/api/booking/?email=alice@wonderland.test')
        self.assertEqual(res_unauthenticated.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_unauthenticated.json()['data']), 0)

        # Request with matching client token returns the booking
        res_authenticated = self.client.get('/api/booking/?email=alice@wonderland.test', HTTP_X_CLIENT_TOKEN="alice_token_private")
        self.assertEqual(res_authenticated.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_authenticated.json()['data']), 1)
        self.assertEqual(res_authenticated.json()['data'][0]['customer_name'], "Alice Wonderland")

    def test_known_obd_lookup_returns_immediate_zero_token_technical_data(self):
        """Test querying known OBD code (e.g., P0300) returns structured diagnosis without AI token consumption."""
        res = self.client.post('/api/chat/', {
            "message": "My Check Engine Light came on with code P0300"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()['data']
        self.assertTrue(data['success'] if 'success' in data else True)
        self.assertFalse(data['is_ai_generated'])
        content = data['assistant_message']['content']
        self.assertIn("P0300", content)
        self.assertIn("Random or Multiple Cylinder Misfire", content)
        self.assertIn("Probable Root Causes", content)

    @patch('api.services.gemini_service.GeminiMechanicService._call_grok_completion')
    def test_grok_ai_fallback_on_gemini_unavailable(self, mock_grok):
        """Test that when Gemini API is unavailable, system cascades to Grok AI fallback."""
        mock_grok.return_value = "Grok Diagnostic Analysis: Spark plug fouling detected on cylinder 3."
        conv = Conversation.objects.create(car_make="Ford", car_model="Focus", car_year="2018")
        
        # When Gemini has no key, it falls through to Grok
        ai_res = GeminiMechanicService.generate_chat_response(conv, "Engine running rough with hesitation on acceleration")
        self.assertTrue(ai_res['is_ai_generated'])
        self.assertEqual(ai_res['text'], "Grok Diagnostic Analysis: Spark plug fouling detected on cylinder 3.")
        mock_grok.assert_called_once()



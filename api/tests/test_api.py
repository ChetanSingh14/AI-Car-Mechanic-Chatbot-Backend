from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
import datetime
from api.models import Conversation, Message, MediaAttachment, Diagnosis, Booking

class CarMechanicAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_chat_non_automotive_query_rejected_without_ai(self):
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

    def test_chat_automotive_query_triggers_mechanic(self):
        """Test valid car query initiates conversation and mechanic response."""
        url = '/api/chat/'
        payload = {
            "message": "My 2018 Honda Civic makes a loud squealing noise when I press the brakes",
            "car_make": "Honda",
            "car_model": "Civic",
            "car_year": "2018"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('conversation_id', data['data'])
        self.assertIn("brake", data['data']['assistant_message']['content'].lower())

    def test_file_upload(self):
        """Test uploading diagnostic image attachment."""
        # Create conversation first
        conv = Conversation.objects.create(car_make="Toyota", car_model="Camry", car_year="2020")
        url = '/api/upload/'
        image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4'
        uploaded_file = SimpleUploadedFile("brake_inspection.png", image_content, content_type="image/png")

        payload = {
            "conversation_id": str(conv.id),
            "file": uploaded_file
        }
        response = self.client.post(url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['file_type'], 'image')

    def test_diagnosis_generation(self):
        """Test diagnosis generation endpoint."""
        conv = Conversation.objects.create(car_make="Ford", car_model="F-150", car_year="2019")
        Message.objects.create(conversation=conv, sender='user', content="The engine is overheating and leaking coolant")

        url = '/api/diagnosis/'
        payload = {"conversation_id": str(conv.id)}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('issue_title', data['data'])
        self.assertEqual(Diagnosis.objects.count(), 1)
        conv.refresh_from_db()
        self.assertEqual(conv.status, 'diagnosed')

    def test_booking_workflow(self):
        """Test mechanics booking creation and retrieval."""
        conv = Conversation.objects.create(car_make="Ford", car_model="Mustang", car_year="2021")
        diag = Diagnosis.objects.create(
            conversation=conv,
            issue_title="Alternator Failure",
            severity="high",
            description="Alternator not charging battery",
            recommended_service="Alternator Replacement",
            estimated_cost="$250 - $400"
        )

        url = '/api/booking/'
        future_date = (timezone.now() + datetime.timedelta(days=2)).strftime('%Y-%m-%d')
        payload = {
            "diagnosis": str(diag.id),
            "customer_name": "John Doe",
            "customer_email": "johndoe@example.com",
            "customer_phone": "+15551234567",
            "preferred_date": future_date,
            "preferred_time": "10:00 AM",
            "notes": "Please provide loaner car if repair takes > 3 hours."
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertTrue(data['success'])
        booking_id = data['data']['id']

        # Get booking detail
        get_url = f'/api/booking/{booking_id}/'
        get_res = self.client.get(get_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        get_data = get_res.json()
        self.assertEqual(get_data['data']['customer_name'], "John Doe")
        self.assertEqual(get_data['data']['diagnosis_detail']['issue_title'], "Alternator Failure")

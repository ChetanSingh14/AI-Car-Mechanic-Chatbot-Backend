import logging
import uuid
from django.utils import timezone
from api.models import Booking, Diagnosis

logger = logging.getLogger(__name__)

class BookingService:
    @classmethod
    def create_booking(cls, diagnosis_id, customer_name, customer_email, customer_phone, preferred_date, preferred_time, notes="", mechanic_name=""):
        try:
            diag_uuid = uuid.UUID(str(diagnosis_id))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Invalid diagnosis UUID provided.")

        try:
            diagnosis = Diagnosis.objects.get(id=diag_uuid)
        except Diagnosis.DoesNotExist:
            raise ValueError(f"Diagnosis with ID {diagnosis_id} does not exist.")

        # Ensure preferred_date is in the future or today
        if preferred_date < timezone.now().date():
            raise ValueError("Preferred booking date cannot be in the past.")

        booking = Booking.objects.create(
            diagnosis=diagnosis,
            mechanic_name=mechanic_name or '',
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            notes=notes or '',
            status='confirmed'
        )

        # Update conversation status to 'booked'
        conversation = diagnosis.conversation
        conversation.status = 'booked'
        conversation.save()

        logger.info(f"Mechanic booking created successfully: #{booking.id} for {customer_name} (Mechanic: {mechanic_name})")
        return booking

    @classmethod
    def get_booking_details(cls, booking_id):
        try:
            val_uuid = uuid.UUID(str(booking_id))
            return Booking.objects.select_related('diagnosis', 'diagnosis__conversation').get(id=val_uuid)
        except (ValueError, TypeError, Booking.DoesNotExist):
            return None

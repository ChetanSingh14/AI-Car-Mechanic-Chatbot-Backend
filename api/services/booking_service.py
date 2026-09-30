import logging
from django.utils import timezone
from api.models import Booking, Diagnosis

logger = logging.getLogger(__name__)

class BookingService:
    @classmethod
    def create_booking(cls, diagnosis_id, customer_name, customer_email, customer_phone, preferred_date, preferred_time, notes=""):
        try:
            diagnosis = Diagnosis.objects.get(id=diagnosis_id)
        except Diagnosis.DoesNotExist:
            raise ValueError(f"Diagnosis with ID {diagnosis_id} does not exist.")

        # Ensure preferred_date is in the future or today
        if preferred_date < timezone.now().date():
            raise ValueError("Preferred booking date cannot be in the past.")

        booking = Booking.objects.create(
            diagnosis=diagnosis,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            notes=notes,
            status='confirmed'
        )

        # Update conversation status to 'booked'
        conversation = diagnosis.conversation
        conversation.status = 'booked'
        conversation.save()

        logger.info(f"Mechanic booking created successfully: #{booking.id} for {customer_name}")
        return booking

    @classmethod
    def get_booking_details(cls, booking_id):
        try:
            return Booking.objects.select_related('diagnosis', 'diagnosis__conversation').get(id=booking_id)
        except Booking.DoesNotExist:
            return None

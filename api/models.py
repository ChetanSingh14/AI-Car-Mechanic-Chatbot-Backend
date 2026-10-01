import uuid
from django.db import models

class Conversation(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active Troubleshooting'),
        ('diagnosed', 'Diagnosis Completed'),
        ('booked', 'Mechanic Booked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    car_make = models.CharField(max_length=50, blank=True, null=True)
    car_model = models.CharField(max_length=50, blank=True, null=True)
    car_year = models.CharField(max_length=10, blank=True, null=True)
    symptom_category = models.CharField(max_length=50, blank=True, null=True)
    client_token = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        car_str = f"{self.car_year or ''} {self.car_make or ''} {self.car_model or ''}".strip()
        return f"Conversation {self.id} ({car_str or 'Unknown Vehicle'})"


class Message(models.Model):
    SENDER_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=20, choices=SENDER_CHOICES)
    content = models.TextField()
    is_ai_generated = models.BooleanField(default=False, help_text="Flag to track whether AI API was called")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.sender}] {self.content[:30]}..."


class MediaAttachment(models.Model):
    TYPE_CHOICES = [
        ('image', 'Image'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='media_attachments')
    message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True, related_name='media_attachments')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    file_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    original_name = models.CharField(max_length=255)
    analysis_summary = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.file_type.upper()}: {self.original_name}"


class Diagnosis(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low / Routine Maintenance'),
        ('medium', 'Medium / Attention Soon'),
        ('high', 'High / Urgent Repair Needed'),
        ('critical', 'Critical / Do Not Drive'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.OneToOneField(Conversation, on_delete=models.CASCADE, related_name='diagnosis')
    issue_title = models.CharField(max_length=200)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    description = models.TextField()
    recommended_service = models.CharField(max_length=200)
    estimated_cost = models.CharField(max_length=100, default="$100 - $300")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Diagnosis: {self.issue_title} ({self.severity})"


class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    diagnosis = models.ForeignKey(Diagnosis, on_delete=models.CASCADE, related_name='bookings')
    mechanic_name = models.CharField(max_length=255, blank=True, default='')
    customer_name = models.CharField(max_length=100)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    preferred_date = models.DateField()
    preferred_time = models.CharField(max_length=50)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking #{self.id} for {self.customer_name} ({self.status})"

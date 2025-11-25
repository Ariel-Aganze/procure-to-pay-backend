from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class DocumentTemplate(models.Model):
    """
    Templates for generating documents
    """
    class TemplateType(models.TextChoices):
        PURCHASE_ORDER = 'purchase_order', 'Purchase Order'
        INVOICE = 'invoice', 'Invoice'
        RECEIPT = 'receipt', 'Receipt'
    
    name = models.CharField(max_length=200)
    template_type = models.CharField(max_length=20, choices=TemplateType.choices)
    template_content = models.TextField(help_text="HTML template with placeholders")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'document_templates'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class AIProcessingJob(models.Model):
    """
    Track AI processing jobs
    """
    class JobType(models.TextChoices):
        EXTRACT_PROFORMA = 'extract_proforma', 'Extract Proforma Data'
        GENERATE_PO = 'generate_po', 'Generate Purchase Order'
        VALIDATE_RECEIPT = 'validate_receipt', 'Validate Receipt'
        EXTRACT_TEXT = 'extract_text', 'Extract Text from Document'
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_type = models.CharField(max_length=20, choices=JobType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Input data
    input_file = models.FileField(upload_to='ai_processing/inputs/', blank=True, null=True)
    input_data = models.JSONField(default=dict, blank=True)
    
    # Output data
    output_data = models.JSONField(default=dict, blank=True)
    output_file = models.FileField(upload_to='ai_processing/outputs/', blank=True, null=True)
    
    # Processing information
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    processing_time = models.FloatField(null=True, blank=True, help_text="Time in seconds")
    
    # Error handling
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    
    # Relationships
    purchase_request = models.ForeignKey(
        'purchases.PurchaseRequest',
        on_delete=models.CASCADE,
        related_name='ai_jobs',
        null=True,
        blank=True
    )
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ai_processing_jobs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_job_type_display()} - {self.get_status_display()}"


class ExtractedDocumentData(models.Model):
    """
    Store extracted data from documents
    """
    class DocumentType(models.TextChoices):
        PROFORMA = 'proforma', 'Proforma Invoice'
        PURCHASE_ORDER = 'purchase_order', 'Purchase Order'
        RECEIPT = 'receipt', 'Receipt'
        INVOICE = 'invoice', 'Invoice'
    
    processing_job = models.OneToOneField(
        AIProcessingJob,
        on_delete=models.CASCADE,
        related_name='extracted_data'
    )
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    
    # Vendor information
    vendor_name = models.CharField(max_length=200, blank=True)
    vendor_address = models.TextField(blank=True)
    vendor_email = models.EmailField(blank=True)
    vendor_phone = models.CharField(max_length=20, blank=True)
    
    # Document details
    document_number = models.CharField(max_length=100, blank=True)
    document_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    
    # Financial information
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default='USD')
    
    # Items (stored as JSON)
    line_items = models.JSONField(default=list, blank=True)
    
    # Additional extracted data
    terms_and_conditions = models.TextField(blank=True)
    payment_terms = models.CharField(max_length=200, blank=True)
    delivery_terms = models.CharField(max_length=200, blank=True)
    
    # Quality metrics
    confidence_score = models.FloatField(null=True, blank=True, help_text="AI confidence (0-1)")
    extraction_quality = models.CharField(
        max_length=20,
        choices=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('poor', 'Poor')
        ],
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'extracted_document_data'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_document_type_display()} - {self.vendor_name}"


class DocumentValidationResult(models.Model):
    """
    Store validation results when comparing documents
    """
    class ValidationStatus(models.TextChoices):
        PASSED = 'passed', 'Passed'
        FAILED = 'failed', 'Failed'
        WARNING = 'warning', 'Warning'
        REQUIRES_REVIEW = 'requires_review', 'Requires Review'
    
    processing_job = models.OneToOneField(
        AIProcessingJob,
        on_delete=models.CASCADE,
        related_name='validation_result'
    )
    
    validation_status = models.CharField(max_length=20, choices=ValidationStatus.choices)
    overall_score = models.FloatField(help_text="Overall validation score (0-1)")
    
    # Comparison results
    vendor_match = models.BooleanField(default=False)
    amount_match = models.BooleanField(default=False)
    items_match = models.BooleanField(default=False)
    date_valid = models.BooleanField(default=False)
    
    # Detailed results
    discrepancies = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    
    # Reference documents (what we compared against)
    reference_po = models.ForeignKey(
        'purchases.PurchaseRequest',
        on_delete=models.CASCADE,
        related_name='validation_results'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'document_validation_results'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Validation: {self.get_validation_status_display()}"
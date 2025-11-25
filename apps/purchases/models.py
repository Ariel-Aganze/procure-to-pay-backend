from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils import timezone
import uuid

User = get_user_model()


class PurchaseRequest(models.Model):
    """
    Main purchase request model with approval workflow
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
    
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, help_text="Brief title of the purchase request")
    description = models.TextField(help_text="Detailed description of items/services needed")
    
    # Financial Information
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Total amount in USD"
    )
    
    # Status and Priority
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    
    # User Relationships
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='purchase_requests',
        help_text="User who created the request"
    )
    
    # Approval Information
    approved_by = models.ManyToManyField(
        User,
        through='Approval',
        related_name='approved_requests',
        blank=True
    )
    
    # File Attachments
    proforma = models.FileField(
        upload_to='proformas/',
        blank=True,
        null=True,
        help_text="Proforma invoice or quotation"
    )
    
    purchase_order = models.FileField(
        upload_to='purchase_orders/',
        blank=True,
        null=True,
        help_text="Generated purchase order"
    )
    
    receipt = models.FileField(
        upload_to='receipts/',
        blank=True,
        null=True,
        help_text="Purchase receipt for validation"
    )
    
    # Additional Information
    vendor_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Vendor/supplier name"
    )
    
    vendor_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Vendor contact email"
    )
    
    expected_delivery_date = models.DateField(
        blank=True,
        null=True,
        help_text="Expected delivery date"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # AI Processing Status
    proforma_processed = models.BooleanField(default=False)
    po_generated = models.BooleanField(default=False)
    receipt_validated = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'purchase_requests'
        ordering = ['-created_at']
        verbose_name = 'Purchase Request'
        verbose_name_plural = 'Purchase Requests'
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    @property
    def can_be_edited(self):
        """Check if request can still be edited"""
        return self.status == self.Status.PENDING
    
    @property
    def is_fully_approved(self):
        """Check if request has all required approvals"""
        required_approvals = self.get_required_approval_levels()
        current_approvals = set(
            self.approvals.filter(approved=True).values_list('approval_level', flat=True)
        )
        return required_approvals.issubset(current_approvals)
    
    def get_required_approval_levels(self):
        """Get required approval levels based on amount"""
        if self.amount <= 1000:
            return {1}  # Only Level 1 approval needed
        elif self.amount <= 10000:
            return {1, 2}  # Both Level 1 and 2 needed
        else:
            return {1, 2}  # For now, max 2 levels
    
    def get_pending_approvers(self):
        """Get users who can provide next approval"""
        required_levels = self.get_required_approval_levels()
        approved_levels = set(
            self.approvals.filter(approved=True).values_list('approval_level', flat=True)
        )
        pending_levels = required_levels - approved_levels
        
        if not pending_levels:
            return User.objects.none()
        
        next_level = min(pending_levels)
        
        # Get users who can approve at this level
        if next_level == 1:
            return User.objects.filter(
                role__in=[User.Role.APPROVER_LEVEL_1, User.Role.APPROVER_LEVEL_2, User.Role.ADMIN]
            )
        elif next_level == 2:
            return User.objects.filter(
                role__in=[User.Role.APPROVER_LEVEL_2, User.Role.ADMIN]
            )
        
        return User.objects.none()


class Approval(models.Model):
    """
    Through model for approval tracking
    """
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name='approvals'
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT
    )
    approval_level = models.IntegerField(help_text="Approval level (1, 2, etc.)")
    approved = models.BooleanField(default=True)
    comments = models.TextField(blank=True, help_text="Approval/rejection comments")
    approved_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'approvals'
        unique_together = ['purchase_request', 'approval_level']
        ordering = ['approval_level', 'approved_at']
    
    def __str__(self):
        status = "Approved" if self.approved else "Rejected"
        return f"{self.purchase_request.title} - Level {self.approval_level} {status}"


class RequestItem(models.Model):
    """
    Individual items within a purchase request
    """
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name='items'
    )
    description = models.CharField(max_length=500)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False
    )
    
    # Specifications
    brand = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    specifications = models.TextField(blank=True)
    
    class Meta:
        db_table = 'request_items'
        ordering = ['id']
    
    def save(self, *args, **kwargs):
        """Auto-calculate total price"""
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.description} x{self.quantity}"


class DocumentProcessingLog(models.Model):
    """
    Log of AI document processing activities
    """
    
    class ProcessType(models.TextChoices):
        PROFORMA_EXTRACT = 'proforma_extract', 'Proforma Extraction'
        PO_GENERATION = 'po_generation', 'PO Generation'
        RECEIPT_VALIDATION = 'receipt_validation', 'Receipt Validation'
    
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name='processing_logs'
    )
    process_type = models.CharField(max_length=20, choices=ProcessType.choices)
    status = models.CharField(max_length=20, default='processing')
    input_file = models.CharField(max_length=500, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    processing_time = models.FloatField(null=True, blank=True, help_text="Time in seconds")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'document_processing_logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_process_type_display()} - {self.purchase_request.title}"
from rest_framework import serializers
from .models import (
    DocumentTemplate, 
    AIProcessingJob, 
    ExtractedDocumentData, 
    DocumentValidationResult
)


class DocumentTemplateSerializer(serializers.ModelSerializer):
    """
    Serializer for document templates
    """
    class Meta:
        model = DocumentTemplate
        fields = [
            'id', 'name', 'template_type', 'template_content',
            'is_active', 'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class AIProcessingJobSerializer(serializers.ModelSerializer):
    """
    Serializer for AI processing jobs
    """
    job_type_display = serializers.CharField(source='get_job_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = AIProcessingJob
        fields = [
            'id', 'job_type', 'job_type_display', 'status', 'status_display',
            'input_file', 'input_data', 'output_data', 'output_file',
            'started_at', 'completed_at', 'processing_time',
            'error_message', 'retry_count', 'max_retries',
            'purchase_request', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'started_at', 'completed_at', 'processing_time',
            'error_message', 'retry_count', 'output_data', 'output_file',
            'created_by', 'created_at', 'updated_at'
        ]


class ExtractedDocumentDataSerializer(serializers.ModelSerializer):
    """
    Serializer for extracted document data
    """
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    extraction_quality_display = serializers.CharField(source='get_extraction_quality_display', read_only=True)
    
    class Meta:
        model = ExtractedDocumentData
        fields = [
            'id', 'processing_job', 'document_type', 'document_type_display',
            'vendor_name', 'vendor_address', 'vendor_email', 'vendor_phone',
            'document_number', 'document_date', 'due_date',
            'subtotal', 'tax_amount', 'total_amount', 'currency',
            'line_items', 'terms_and_conditions', 'payment_terms', 'delivery_terms',
            'confidence_score', 'extraction_quality', 'extraction_quality_display',
            'created_at'
        ]


class DocumentValidationResultSerializer(serializers.ModelSerializer):
    """
    Serializer for document validation results
    """
    validation_status_display = serializers.CharField(source='get_validation_status_display', read_only=True)
    
    class Meta:
        model = DocumentValidationResult
        fields = [
            'id', 'processing_job', 'validation_status', 'validation_status_display',
            'overall_score', 'vendor_match', 'amount_match', 'items_match', 'date_valid',
            'discrepancies', 'warnings', 'recommendations', 'reference_po',
            'created_at'
        ]


class DocumentProcessingStatusSerializer(serializers.Serializer):
    """
    Serializer for document processing status summary
    """
    proforma_processed = serializers.BooleanField()
    po_generated = serializers.BooleanField()
    receipt_validated = serializers.BooleanField()
    
    # Job statuses
    proforma_job = AIProcessingJobSerializer(read_only=True, allow_null=True)
    po_job = AIProcessingJobSerializer(read_only=True, allow_null=True)
    receipt_job = AIProcessingJobSerializer(read_only=True, allow_null=True)
    
    # Extracted data
    extracted_data = ExtractedDocumentDataSerializer(read_only=True, allow_null=True)
    validation_result = DocumentValidationResultSerializer(read_only=True, allow_null=True)


class ProformaUploadSerializer(serializers.Serializer):
    """
    Serializer for proforma document upload
    """
    proforma = serializers.FileField()
    
    def validate_proforma(self, value):
        # Validate file type
        allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                "Only PDF and image files are allowed for proforma documents"
            )
        
        # Validate file size (10MB limit)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Proforma file too large ( > 10MB )")
        
        return value


class DocumentProcessingTriggerSerializer(serializers.Serializer):
    """
    Serializer for triggering document processing
    """
    job_type = serializers.ChoiceField(choices=AIProcessingJob.JobType.choices)
    force_reprocess = serializers.BooleanField(default=False)


class OllamaStatusSerializer(serializers.Serializer):
    """
    Serializer for Ollama service status
    """
    is_available = serializers.BooleanField()
    host = serializers.CharField()
    model = serializers.CharField()
    last_checked = serializers.DateTimeField()
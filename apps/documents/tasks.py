from celery import shared_task
from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings
import json
import os
import time
import logging
from datetime import datetime, timedelta

from .models import AIProcessingJob, ExtractedDocumentData, DocumentValidationResult
from .services.ollama_service import ollama_service
from apps.purchases.models import PurchaseRequest

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_proforma_document(self, job_id: str):
    """
    Process proforma document to extract structured data
    """
    try:
        job = AIProcessingJob.objects.get(id=job_id)
        job.status = AIProcessingJob.Status.PROCESSING
        job.started_at = timezone.now()
        job.save()
        
        logger.info(f"Starting proforma processing for job {job_id}")
        
        # Check if Ollama is available
        if not ollama_service.is_available():
            raise Exception("Ollama service is not available")
        
        # Extract text from uploaded file
        file_path = job.input_file.path
        extracted_text = ollama_service.extract_text_from_file(file_path)
        
        if not extracted_text.strip():
            raise Exception("No text could be extracted from the document")
        
        # Use AI to extract structured data
        extracted_data = ollama_service.extract_proforma_data(extracted_text)
        
        # Save extracted data
        document_data = ExtractedDocumentData.objects.create(
            processing_job=job,
            document_type=ExtractedDocumentData.DocumentType.PROFORMA,
            vendor_name=extracted_data.get('vendor_name', ''),
            vendor_address=extracted_data.get('vendor_address', ''),
            vendor_email=extracted_data.get('vendor_email', ''),
            vendor_phone=extracted_data.get('vendor_phone', ''),
            document_number=extracted_data.get('document_number', ''),
            subtotal=extracted_data.get('subtotal'),
            tax_amount=extracted_data.get('tax_amount'),
            total_amount=extracted_data.get('total_amount'),
            currency=extracted_data.get('currency', 'USD'),
            line_items=extracted_data.get('line_items', []),
            payment_terms=extracted_data.get('payment_terms', ''),
            delivery_terms=extracted_data.get('delivery_terms', ''),
            confidence_score=0.85,  # You can implement actual confidence calculation
            extraction_quality='good'
        )
        
        # Update job
        job.status = AIProcessingJob.Status.COMPLETED
        job.completed_at = timezone.now()
        job.processing_time = (job.completed_at - job.started_at).total_seconds()
        job.output_data = {
            'extracted_data': extracted_data,
            'extracted_text': extracted_text[:1000],  # First 1000 chars for reference
            'document_data_id': str(document_data.id)
        }
        job.save()
        
        # Update purchase request
        if job.purchase_request:
            job.purchase_request.proforma_processed = True
            # Update vendor info from extracted data
            if extracted_data.get('vendor_name'):
                job.purchase_request.vendor_name = extracted_data['vendor_name']
            if extracted_data.get('vendor_email'):
                job.purchase_request.vendor_email = extracted_data['vendor_email']
            job.purchase_request.save()
        
        logger.info(f"Proforma processing completed for job {job_id}")
        return {
            'status': 'completed',
            'extracted_data': extracted_data,
            'processing_time': job.processing_time
        }
        
    except Exception as e:
        logger.error(f"Error processing proforma for job {job_id}: {str(e)}")
        
        # Update job with error
        job = AIProcessingJob.objects.get(id=job_id)
        job.status = AIProcessingJob.Status.FAILED
        job.error_message = str(e)
        job.retry_count += 1
        job.save()
        
        # Retry if under max retries
        if job.retry_count < job.max_retries:
            logger.info(f"Retrying proforma processing for job {job_id} (attempt {job.retry_count})")
            raise self.retry(countdown=60 * job.retry_count, exc=e)
        
        raise e


@shared_task(bind=True, max_retries=3)
def generate_purchase_order(self, purchase_request_id: str):
    """
    Generate purchase order document from approved purchase request
    """
    try:
        purchase_request = PurchaseRequest.objects.get(id=purchase_request_id)
        
        # Create processing job
        job = AIProcessingJob.objects.create(
            job_type=AIProcessingJob.JobType.GENERATE_PO,
            status=AIProcessingJob.Status.PROCESSING,
            started_at=timezone.now(),
            purchase_request=purchase_request,
            created_by=purchase_request.created_by,
            input_data={
                'purchase_request_id': str(purchase_request_id),
                'title': purchase_request.title,
                'amount': float(purchase_request.amount),
                'vendor_name': purchase_request.vendor_name or ''
            }
        )
        
        logger.info(f"Starting PO generation for request {purchase_request_id}")
        
        # Check if Ollama is available
        if not ollama_service.is_available():
            raise Exception("Ollama service is not available")
        
        # Get proforma data if available
        proforma_data = {}
        if hasattr(purchase_request, 'ai_jobs'):
            proforma_job = purchase_request.ai_jobs.filter(
                job_type=AIProcessingJob.JobType.EXTRACT_PROFORMA,
                status=AIProcessingJob.Status.COMPLETED
            ).first()
            
            if proforma_job and hasattr(proforma_job, 'extracted_data'):
                extracted_data = proforma_job.extracted_data
                proforma_data = {
                    'vendor_name': extracted_data.vendor_name,
                    'vendor_address': extracted_data.vendor_address,
                    'vendor_email': extracted_data.vendor_email,
                    'line_items': extracted_data.line_items,
                    'total_amount': float(extracted_data.total_amount) if extracted_data.total_amount else float(purchase_request.amount),
                    'currency': extracted_data.currency,
                    'payment_terms': extracted_data.payment_terms,
                    'delivery_terms': extracted_data.delivery_terms
                }
        
        # Prepare request data
        request_data = {
            'id': str(purchase_request.id),
            'title': purchase_request.title,
            'description': purchase_request.description,
            'amount': float(purchase_request.amount),
            'priority': purchase_request.priority,
            'vendor_name': purchase_request.vendor_name or '',
            'vendor_email': purchase_request.vendor_email or '',
            'expected_delivery_date': purchase_request.expected_delivery_date.isoformat() if purchase_request.expected_delivery_date else None,
            'created_by': purchase_request.created_by.get_full_name(),
            'created_at': purchase_request.created_at.isoformat()
        }
        
        # Generate PO using AI
        po_data = ollama_service.generate_purchase_order(proforma_data, request_data)
        
        # Create PO document (in a real implementation, you'd generate a PDF)
        po_content = json.dumps(po_data, indent=2)
        
        # Save PO file
        po_filename = f"PO_{purchase_request.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # In a real implementation, you'd generate a proper PDF using reportlab or similar
        # For now, we'll save the JSON data
        purchase_request.purchase_order.save(
            po_filename,
            ContentFile(po_content.encode('utf-8')),
            save=True
        )
        
        # Update job
        job.status = AIProcessingJob.Status.COMPLETED
        job.completed_at = timezone.now()
        job.processing_time = (job.completed_at - job.started_at).total_seconds()
        job.output_data = po_data
        job.save()
        
        # Update purchase request
        purchase_request.po_generated = True
        purchase_request.save()
        
        logger.info(f"PO generation completed for request {purchase_request_id}")
        return {
            'status': 'completed',
            'po_data': po_data,
            'po_file': purchase_request.purchase_order.url,
            'processing_time': job.processing_time
        }
        
    except Exception as e:
        logger.error(f"Error generating PO for request {purchase_request_id}: {str(e)}")
        
        # Update job with error
        if 'job' in locals():
            job.status = AIProcessingJob.Status.FAILED
            job.error_message = str(e)
            job.retry_count += 1
            job.save()
            
            # Retry if under max retries
            if job.retry_count < job.max_retries:
                logger.info(f"Retrying PO generation for request {purchase_request_id} (attempt {job.retry_count})")
                raise self.retry(countdown=60 * job.retry_count, exc=e)
        
        raise e


@shared_task(bind=True, max_retries=3)
def validate_receipt_document(self, purchase_request_id: str):
    """
    Validate uploaded receipt against purchase order
    """
    try:
        purchase_request = PurchaseRequest.objects.get(id=purchase_request_id)
        
        if not purchase_request.receipt:
            raise Exception("No receipt file found for validation")
        
        # Create processing job
        job = AIProcessingJob.objects.create(
            job_type=AIProcessingJob.JobType.VALIDATE_RECEIPT,
            status=AIProcessingJob.Status.PROCESSING,
            started_at=timezone.now(),
            purchase_request=purchase_request,
            created_by=purchase_request.created_by,
            input_file=purchase_request.receipt,
            input_data={
                'purchase_request_id': str(purchase_request_id),
                'receipt_filename': purchase_request.receipt.name
            }
        )
        
        logger.info(f"Starting receipt validation for request {purchase_request_id}")
        
        # Check if Ollama is available
        if not ollama_service.is_available():
            raise Exception("Ollama service is not available")
        
        # Extract text from receipt
        receipt_text = ollama_service.extract_text_from_file(purchase_request.receipt.path)
        
        if not receipt_text.strip():
            raise Exception("No text could be extracted from the receipt")
        
        # Extract receipt data
        receipt_data = ollama_service.extract_proforma_data(receipt_text)  # Same structure as proforma
        
        # Get PO data for comparison
        po_data = {}
        if purchase_request.purchase_order:
            try:
                # In our implementation, PO is stored as JSON
                po_content = purchase_request.purchase_order.read().decode('utf-8')
                po_data = json.loads(po_content)
            except Exception as e:
                logger.warning(f"Could not parse PO data: {str(e)}")
                # Fallback to basic request data
                po_data = {
                    'vendor_name': purchase_request.vendor_name or '',
                    'total_amount': float(purchase_request.amount),
                    'currency': 'USD'
                }
        
        # Validate receipt against PO
        validation_result = ollama_service.validate_receipt(receipt_data, po_data)
        
        # Save validation result
        validation_record = DocumentValidationResult.objects.create(
            processing_job=job,
            validation_status=validation_result.get('validation_status', 'requires_review'),
            overall_score=validation_result.get('overall_score', 0.5),
            vendor_match=validation_result.get('vendor_match', False),
            amount_match=validation_result.get('amount_match', False),
            items_match=validation_result.get('items_match', False),
            date_valid=validation_result.get('date_valid', True),
            discrepancies=validation_result.get('discrepancies', []),
            warnings=validation_result.get('warnings', []),
            recommendations=validation_result.get('recommendations', []),
            reference_po=purchase_request
        )
        
        # Update job
        job.status = AIProcessingJob.Status.COMPLETED
        job.completed_at = timezone.now()
        job.processing_time = (job.completed_at - job.started_at).total_seconds()
        job.output_data = {
            'receipt_data': receipt_data,
            'validation_result': validation_result,
            'validation_record_id': str(validation_record.id)
        }
        job.save()
        
        # Update purchase request
        purchase_request.receipt_validated = True
        purchase_request.save()
        
        logger.info(f"Receipt validation completed for request {purchase_request_id}")
        return {
            'status': 'completed',
            'validation_result': validation_result,
            'processing_time': job.processing_time
        }
        
    except Exception as e:
        logger.error(f"Error validating receipt for request {purchase_request_id}: {str(e)}")
        
        # Update job with error
        if 'job' in locals():
            job.status = AIProcessingJob.Status.FAILED
            job.error_message = str(e)
            job.retry_count += 1
            job.save()
            
            # Retry if under max retries
            if job.retry_count < job.retry_count:
                logger.info(f"Retrying receipt validation for request {purchase_request_id} (attempt {job.retry_count})")
                raise self.retry(countdown=60 * job.retry_count, exc=e)
        
        raise e


@shared_task
def cleanup_old_processing_jobs():
    """
    Clean up old processing jobs and temporary files
    """
    try:
        # Delete completed jobs older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        old_jobs = AIProcessingJob.objects.filter(
            created_at__lt=cutoff_date,
            status=AIProcessingJob.Status.COMPLETED
        )
        
        deleted_count = 0
        for job in old_jobs:
            # Clean up files
            if job.input_file:
                if os.path.exists(job.input_file.path):
                    os.remove(job.input_file.path)
            if job.output_file:
                if os.path.exists(job.output_file.path):
                    os.remove(job.output_file.path)
            
            job.delete()
            deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} old processing jobs")
        return {'cleaned_jobs': deleted_count}
        
    except Exception as e:
        logger.error(f"Error cleaning up processing jobs: {str(e)}")
        raise e
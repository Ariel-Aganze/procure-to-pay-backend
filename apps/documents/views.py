from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import (
    DocumentTemplate, 
    AIProcessingJob, 
    ExtractedDocumentData, 
    DocumentValidationResult
)
from .serializers import (
    DocumentTemplateSerializer,
    AIProcessingJobSerializer,
    ExtractedDocumentDataSerializer,
    DocumentValidationResultSerializer,
    DocumentProcessingStatusSerializer,
    ProformaUploadSerializer,
    DocumentProcessingTriggerSerializer,
    OllamaStatusSerializer
)
from .tasks import (
    process_proforma_document,
    generate_purchase_order,
    validate_receipt_document
)
from .services.ollama_service import ollama_service
from apps.purchases.models import PurchaseRequest
from apps.accounts.permissions import IsFinanceUser, CanAccessPurchaseRequest


class DocumentProcessingStatusView(APIView):
    """
    Get document processing status for a purchase request
    """
    permission_classes = [permissions.IsAuthenticated, CanAccessPurchaseRequest]
    
    @swagger_auto_schema(
        operation_description="Get document processing status for a purchase request",
        responses={200: DocumentProcessingStatusSerializer}
    )
    def get(self, request, pk):
        purchase_request = get_object_or_404(PurchaseRequest, pk=pk)
        
        # Get processing jobs
        proforma_job = purchase_request.ai_jobs.filter(
            job_type=AIProcessingJob.JobType.EXTRACT_PROFORMA
        ).order_by('-created_at').first()
        
        po_job = purchase_request.ai_jobs.filter(
            job_type=AIProcessingJob.JobType.GENERATE_PO
        ).order_by('-created_at').first()
        
        receipt_job = purchase_request.ai_jobs.filter(
            job_type=AIProcessingJob.JobType.VALIDATE_RECEIPT
        ).order_by('-created_at').first()
        
        # Get extracted data and validation results
        extracted_data = None
        validation_result = None
        
        if proforma_job and hasattr(proforma_job, 'extracted_data'):
            extracted_data = proforma_job.extracted_data
        
        if receipt_job and hasattr(receipt_job, 'validation_result'):
            validation_result = receipt_job.validation_result
        
        # Prepare status data
        status_data = {
            'proforma_processed': purchase_request.proforma_processed,
            'po_generated': purchase_request.po_generated,
            'receipt_validated': purchase_request.receipt_validated,
            'proforma_job': proforma_job,
            'po_job': po_job,
            'receipt_job': receipt_job,
            'extracted_data': extracted_data,
            'validation_result': validation_result
        }
        
        serializer = DocumentProcessingStatusSerializer(status_data, context={'request': request})
        return Response(serializer.data)


class ProformaUploadView(APIView):
    """
    Upload and process proforma document
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Upload proforma document and trigger processing",
        request_body=ProformaUploadSerializer,
        responses={
            201: "Proforma uploaded and processing started",
            400: "Bad Request",
            403: "Forbidden"
        }
    )
    def post(self, request, pk):
        purchase_request = get_object_or_404(PurchaseRequest, pk=pk)
        
        # Check if user can upload proforma (owner only)
        if purchase_request.created_by != request.user:
            return Response(
                {'error': 'You can only upload proforma for your own requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if request is still pending
        if purchase_request.status != PurchaseRequest.Status.PENDING:
            return Response(
                {'error': 'Proforma can only be uploaded for pending requests'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ProformaUploadSerializer(data=request.data)
        if serializer.is_valid():
            # Update purchase request with proforma
            purchase_request.proforma = serializer.validated_data['proforma']
            purchase_request.save()
            
            # Create processing job
            job = AIProcessingJob.objects.create(
                job_type=AIProcessingJob.JobType.EXTRACT_PROFORMA,
                input_file=purchase_request.proforma,
                purchase_request=purchase_request,
                created_by=request.user,
                input_data={
                    'purchase_request_id': str(purchase_request.id),
                    'filename': purchase_request.proforma.name
                }
            )
            
            # Trigger background processing
            process_proforma_document.delay(str(job.id))
            
            return Response({
                'message': 'Proforma uploaded successfully. Processing started.',
                'job_id': str(job.id),
                'proforma_url': request.build_absolute_uri(purchase_request.proforma.url)
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TriggerDocumentProcessingView(APIView):
    """
    Trigger document processing for a purchase request
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Trigger document processing",
        request_body=DocumentProcessingTriggerSerializer,
        responses={
            200: "Processing triggered successfully",
            400: "Bad Request",
            403: "Forbidden"
        }
    )
    def post(self, request, pk):
        purchase_request = get_object_or_404(PurchaseRequest, pk=pk)
        
        serializer = DocumentProcessingTriggerSerializer(data=request.data)
        if serializer.is_valid():
            job_type = serializer.validated_data['job_type']
            force_reprocess = serializer.validated_data['force_reprocess']
            
            # Check permissions based on job type
            if job_type == AIProcessingJob.JobType.EXTRACT_PROFORMA:
                if purchase_request.created_by != request.user:
                    return Response(
                        {'error': 'You can only trigger proforma processing for your own requests'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                if not purchase_request.proforma:
                    return Response(
                        {'error': 'No proforma file uploaded'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            elif job_type == AIProcessingJob.JobType.GENERATE_PO:
                if not request.user.can_access_finance():
                    return Response(
                        {'error': 'Only finance team can trigger PO generation'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                if purchase_request.status != PurchaseRequest.Status.APPROVED:
                    return Response(
                        {'error': 'PO can only be generated for approved requests'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            elif job_type == AIProcessingJob.JobType.VALIDATE_RECEIPT:
                if not (purchase_request.created_by == request.user or request.user.can_access_finance()):
                    return Response(
                        {'error': 'You cannot trigger receipt validation for this request'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                if not purchase_request.receipt:
                    return Response(
                        {'error': 'No receipt file uploaded'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Check if already processed (unless force reprocess)
            existing_job = purchase_request.ai_jobs.filter(
                job_type=job_type,
                status=AIProcessingJob.Status.COMPLETED
            ).first()
            
            if existing_job and not force_reprocess:
                return Response(
                    {'error': 'This document has already been processed. Use force_reprocess=true to reprocess.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create and trigger job
            if job_type == AIProcessingJob.JobType.EXTRACT_PROFORMA:
                job = AIProcessingJob.objects.create(
                    job_type=job_type,
                    input_file=purchase_request.proforma,
                    purchase_request=purchase_request,
                    created_by=request.user
                )
                process_proforma_document.delay(str(job.id))
            
            elif job_type == AIProcessingJob.JobType.GENERATE_PO:
                generate_purchase_order.delay(str(purchase_request.id))
                job = purchase_request.ai_jobs.filter(job_type=job_type).order_by('-created_at').first()
            
            elif job_type == AIProcessingJob.JobType.VALIDATE_RECEIPT:
                validate_receipt_document.delay(str(purchase_request.id))
                job = purchase_request.ai_jobs.filter(job_type=job_type).order_by('-created_at').first()
            
            return Response({
                'message': f'{job.get_job_type_display()} processing triggered successfully',
                'job_id': str(job.id)
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AIProcessingJobListView(generics.ListAPIView):
    """
    List AI processing jobs
    """
    serializer_class = AIProcessingJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.can_access_finance():
            # Finance can see all jobs
            queryset = AIProcessingJob.objects.all()
        else:
            # Users can only see jobs for their own requests
            queryset = AIProcessingJob.objects.filter(
                purchase_request__created_by=user
            )
        
        # Filter by job type
        job_type = self.request.query_params.get('job_type')
        if job_type:
            queryset = queryset.filter(job_type=job_type)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by purchase request
        purchase_request_id = self.request.query_params.get('purchase_request')
        if purchase_request_id:
            queryset = queryset.filter(purchase_request_id=purchase_request_id)
        
        return queryset.order_by('-created_at')


class AIProcessingJobDetailView(generics.RetrieveAPIView):
    """
    Get AI processing job details
    """
    serializer_class = AIProcessingJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.can_access_finance():
            return AIProcessingJob.objects.all()
        else:
            return AIProcessingJob.objects.filter(
                purchase_request__created_by=user
            )


class ExtractedDataListView(generics.ListAPIView):
    """
    List extracted document data
    """
    serializer_class = ExtractedDocumentDataSerializer
    permission_classes = [permissions.IsAuthenticated, IsFinanceUser]
    
    def get_queryset(self):
        queryset = ExtractedDocumentData.objects.all()
        
        # Filter by document type
        document_type = self.request.query_params.get('document_type')
        if document_type:
            queryset = queryset.filter(document_type=document_type)
        
        # Filter by vendor
        vendor = self.request.query_params.get('vendor')
        if vendor:
            queryset = queryset.filter(vendor_name__icontains=vendor)
        
        return queryset.order_by('-created_at')


class ValidationResultListView(generics.ListAPIView):
    """
    List document validation results
    """
    serializer_class = DocumentValidationResultSerializer
    permission_classes = [permissions.IsAuthenticated, IsFinanceUser]
    
    def get_queryset(self):
        queryset = DocumentValidationResult.objects.all()
        
        # Filter by validation status
        validation_status = self.request.query_params.get('validation_status')
        if validation_status:
            queryset = queryset.filter(validation_status=validation_status)
        
        return queryset.order_by('-created_at')


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def ollama_status(request):
    """
    Check Ollama service status
    """
    try:
        is_available = ollama_service.is_available()
        
        status_data = {
            'is_available': is_available,
            'host': ollama_service.base_url,
            'model': ollama_service.model,
            'last_checked': timezone.now()
        }
        
        serializer = OllamaStatusSerializer(status_data)
        return Response(serializer.data)
    
    except Exception as e:
        return Response({
            'error': f'Failed to check Ollama status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsFinanceUser])
def document_processing_stats(request):
    """
    Get document processing statistics
    """
    try:
        stats = {
            'total_jobs': AIProcessingJob.objects.count(),
            'completed_jobs': AIProcessingJob.objects.filter(
                status=AIProcessingJob.Status.COMPLETED
            ).count(),
            'failed_jobs': AIProcessingJob.objects.filter(
                status=AIProcessingJob.Status.FAILED
            ).count(),
            'pending_jobs': AIProcessingJob.objects.filter(
                status__in=[AIProcessingJob.Status.PENDING, AIProcessingJob.Status.PROCESSING]
            ).count(),
        }
        
        # Job type breakdown
        stats['job_types'] = {}
        for job_type, display_name in AIProcessingJob.JobType.choices:
            stats['job_types'][job_type] = {
                'display_name': display_name,
                'total': AIProcessingJob.objects.filter(job_type=job_type).count(),
                'completed': AIProcessingJob.objects.filter(
                    job_type=job_type,
                    status=AIProcessingJob.Status.COMPLETED
                ).count()
            }
        
        # Recent activity
        recent_jobs = AIProcessingJob.objects.filter(
            created_at__gte=timezone.now().replace(hour=0, minute=0, second=0)
        )
        stats['today'] = {
            'total_jobs': recent_jobs.count(),
            'completed_jobs': recent_jobs.filter(
                status=AIProcessingJob.Status.COMPLETED
            ).count(),
            'failed_jobs': recent_jobs.filter(
                status=AIProcessingJob.Status.FAILED
            ).count()
        }
        
        # Validation statistics
        validation_results = DocumentValidationResult.objects.all()
        stats['validations'] = {
            'total': validation_results.count(),
            'passed': validation_results.filter(
                validation_status=DocumentValidationResult.ValidationStatus.PASSED
            ).count(),
            'failed': validation_results.filter(
                validation_status=DocumentValidationResult.ValidationStatus.FAILED
            ).count(),
            'warnings': validation_results.filter(
                validation_status=DocumentValidationResult.ValidationStatus.WARNING
            ).count()
        }
        
        return Response(stats)
    
    except Exception as e:
        return Response({
            'error': f'Failed to get processing stats: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
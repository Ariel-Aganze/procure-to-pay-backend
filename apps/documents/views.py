from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.core.files.storage import default_storage
import hashlib
import os
import json
import logging
from .services import document_service

logger = logging.getLogger(__name__)

class CometStatusView(APIView):
    """Check Comet AI service status with real capabilities"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            status_info = document_service.get_status()
            return Response(status_info)
        except Exception as e:
            return Response({
                'available': False,
                'status': 'error',
                'error': str(e),
                'provider': 'Comet AI (Cohere)'
            }, status=500)

class UploadProformaView(APIView):
    """Upload and store proforma document for processing"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, request_id):
        try:
            if 'proforma' not in request.FILES:
                return Response({
                    'error': 'No proforma file uploaded'
                }, status=400)
            
            file = request.FILES['proforma']
            
            # Handle null request_id
            if request_id is None or str(request_id).lower() == 'null':
                request_id = f"temp_{hash(str(request.user.id) + file.name) % 100000}"
            
            # Validate file
            max_size = getattr(settings, 'DOCUMENT_MAX_SIZE', 10485760)  # 10MB
            if file.size > max_size:
                return Response({
                    'error': f'File size exceeds {max_size / (1024*1024):.0f}MB limit'
                }, status=400)
            
            allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
            if file.content_type not in allowed_types:
                return Response({
                    'error': f'Invalid file type: {file.content_type}. Only PDF, JPG, PNG are allowed'
                }, status=400)
            
            # Save file to storage
            file_name = f'proformas/request_{request_id}_{file.name}'
            file_path = default_storage.save(file_name, file)
            full_file_path = default_storage.path(file_path)
            
            logger.info(f"File uploaded successfully: {full_file_path}")
            
            # Store upload info in session
            uploaded_files = getattr(request.session, 'uploaded_files', {})
            uploaded_files[str(request_id)] = {
                'file_path': file_path,
                'full_file_path': full_file_path,
                'file_name': file.name,
                'file_size': file.size,
                'content_type': file.content_type
            }
            request.session['uploaded_files'] = uploaded_files
            
            return Response({
                'success': True,
                'file_path': file_path,
                'full_path': full_file_path,
                'file_name': file.name,
                'file_size': file.size,
                'content_type': file.content_type,
                'request_id': request_id,
                'message': 'Proforma uploaded successfully - ready for AI processing'
            })
            
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return Response({
                'error': f'Upload failed: {str(e)}'
            }, status=500)

class ProcessDocumentView(APIView):
    """Process uploaded documents with real AI extraction"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, request_id):
        try:
            document_type = request.data.get('document_type', 'proforma')
            processing_type = request.data.get('processing_type', 'extract_data')
            file_path = request.data.get('file_path')
            
            logger.info(f"Processing request - Type: {document_type}, File: {file_path}, RequestID: {request_id}")
            
            # Handle null request_id
            if request_id is None or str(request_id).lower() == 'null':
                request_id = f"temp_{hash(str(request.user.id)) % 100000}"
            
            # Validate document type
            if document_type not in ['proforma', 'receipt']:
                return Response({
                    'error': 'Invalid document type. Must be "proforma" or "receipt"'
                }, status=400)
            
            # Get file path from upload info or request data
            full_file_path = None
            
            if file_path:
                # Use provided file path
                if file_path.startswith('/'):
                    full_file_path = file_path
                else:
                    full_file_path = os.path.join(settings.MEDIA_ROOT, file_path)
            else:
                # Try to get from session
                uploaded_files = getattr(request.session, 'uploaded_files', {})
                file_info = uploaded_files.get(str(request_id))
                
                if file_info:
                    full_file_path = file_info['full_file_path']
                else:
                    # Try to find the most recent upload
                    try:
                        import glob
                        upload_pattern = os.path.join(settings.MEDIA_ROOT, 'proformas', f'request_{request_id}_*')
                        recent_files = glob.glob(upload_pattern)
                        
                        if recent_files:
                            full_file_path = max(recent_files, key=os.path.getctime)
                            logger.info(f"Found recent file: {full_file_path}")
                        else:
                            return Response({
                                'error': 'No uploaded file found. Please upload a document first.'
                            }, status=400)
                            
                    except Exception as e:
                        logger.error(f"Error finding upload: {e}")
                        return Response({
                            'error': f'Could not locate uploaded file: {str(e)}'
                        }, status=400)
            
            if not full_file_path or not os.path.exists(full_file_path):
                return Response({
                    'error': 'Uploaded file not found. Please upload again.'
                }, status=400)
                
            logger.info(f"Processing file: {full_file_path}")
            
            # Generate job ID for tracking
            job_id = f"comet_real_{request_id}_{document_type}_{hash(str(request.user.id) + str(full_file_path)) % 100000}"
            
            # Store processing job info
            processing_jobs = getattr(request.session, 'processing_jobs', {})
            processing_jobs[job_id] = {
                'status': 'queued',
                'document_type': document_type,
                'file_path': full_file_path,
                'user_id': request.user.id,
                'request_id': request_id
            }
            request.session['processing_jobs'] = processing_jobs
            
            logger.info(f"Job queued: {job_id}")
            
            return Response({
                'success': True,
                'job_id': job_id,
                'status': 'queued',
                'message': f'{document_type} processing queued for real AI extraction',
                'estimated_time': '15-45 seconds',
                'file_path': full_file_path
            })
            
        except Exception as e:
            logger.error(f"Processing setup error: {e}", exc_info=True)
            return Response({
                'error': f'Processing setup failed: {str(e)}'
            }, status=500)

class ProcessingStatusView(APIView):
    """Check real processing status and return actual results"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, request_id, job_id):
        try:
            # Get job info from session
            processing_jobs = getattr(request.session, 'processing_jobs', {})
            job_info = processing_jobs.get(job_id)
            
            if not job_info:
                return Response({
                    'status': 'not_found',
                    'error': 'Job not found. May have expired.'
                }, status=404)
            
            # Check if job is already completed
            if job_info.get('status') == 'completed':
                return Response({
                    'status': 'completed',
                    'job_id': job_id,
                    'result': job_info.get('result'),
                    'processing_time': job_info.get('processing_time', 0),
                    'ai_provider': 'Comet AI (Cohere) - Real Extraction'
                })
            
            # Check if job failed
            if job_info.get('status') == 'failed':
                return Response({
                    'status': 'failed',
                    'job_id': job_id,
                    'error': job_info.get('error', 'Unknown error'),
                    'error_data': job_info.get('error_data', {}),
                    'processing_time': job_info.get('processing_time', 0)
                })
            
            # Process the document with real AI
            file_path = job_info['file_path']
            document_type = job_info['document_type']
            
            logger.info(f"Processing document: {file_path} of type: {document_type}")
            
            # Update status to processing
            job_info['status'] = 'processing'
            processing_jobs[job_id] = job_info
            request.session['processing_jobs'] = processing_jobs
            
            # Perform real document processing
            import time
            start_time = time.time()
            
            try:
                # Use the real document processing service
                processing_result = document_service.process_document(
                    file_path=file_path, 
                    document_type=document_type, 
                    request_id=request_id
                )
                
                processing_time = time.time() - start_time
                
                logger.info(f"Processing result: {processing_result}")
                
                if processing_result.get('success'):
                    # Store completed result
                    job_info['status'] = 'completed'
                    job_info['result'] = processing_result['data']
                    job_info['processing_time'] = round(processing_time, 2)
                    processing_jobs[job_id] = job_info
                    request.session['processing_jobs'] = processing_jobs
                    
                    return Response({
                        'status': 'completed',
                        'job_id': job_id,
                        'result': processing_result['data'],
                        'processing_time': round(processing_time, 2),
                        'ai_provider': 'Comet AI (Cohere) - Real Extraction'
                    })
                else:
                    # Processing failed
                    error_data = processing_result.get('data', {})
                    job_info['status'] = 'failed'
                    job_info['error'] = processing_result.get('error', 'Unknown error')
                    job_info['error_data'] = error_data
                    job_info['processing_time'] = round(processing_time, 2)
                    processing_jobs[job_id] = job_info
                    request.session['processing_jobs'] = processing_jobs
                    
                    return Response({
                        'status': 'failed',
                        'job_id': job_id,
                        'error': processing_result.get('error'),
                        'error_data': error_data,
                        'processing_time': round(processing_time, 2)
                    })
                    
            except Exception as processing_error:
                # Processing exception
                processing_time = time.time() - start_time
                error_message = str(processing_error)
                
                logger.error(f"Processing exception: {error_message}", exc_info=True)
                
                job_info['status'] = 'failed'
                job_info['error'] = error_message
                job_info['processing_time'] = round(processing_time, 2)
                processing_jobs[job_id] = job_info
                request.session['processing_jobs'] = processing_jobs
                
                return Response({
                    'status': 'failed',
                    'job_id': job_id,
                    'error': f'Processing error: {error_message}',
                    'processing_time': round(processing_time, 2),
                    'retry_possible': True
                })
                
        except Exception as e:
            logger.error(f"Status check error: {e}", exc_info=True)
            return Response({
                'status': 'error',
                'error': f'Status check failed: {str(e)}'
            }, status=500)

class ProcessingStatsView(APIView):
    """Get real processing statistics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        processing_jobs = getattr(request.session, 'processing_jobs', {})
        
        completed_jobs = [j for j in processing_jobs.values() if j.get('status') == 'completed']
        failed_jobs = [j for j in processing_jobs.values() if j.get('status') == 'failed']
        
        total_jobs = len(processing_jobs)
        success_rate = (len(completed_jobs) / total_jobs * 100) if total_jobs > 0 else 100
        
        avg_time = 0
        if completed_jobs:
            times = [j.get('processing_time', 0) for j in completed_jobs]
            avg_time = sum(times) / len(times) if times else 0
        
        return Response({
            'total_documents_processed': total_jobs,
            'successful_extractions': len(completed_jobs),
            'failed_extractions': len(failed_jobs),
            'success_rate': round(success_rate, 1),
            'average_processing_time': round(avg_time, 2),
            'api_provider': 'Comet AI (Cohere)',
            'processing_type': 'Real AI Extraction',
            'features': [
                'PDF text extraction',
                'Image text recognition', 
                'Real AI analysis',
                'Structured data extraction',
                'Error handling and validation'
            ]
        })

class UploadReceiptView(APIView):
    """Upload receipt for validation"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, request_id):
        try:
            if 'receipt' not in request.FILES:
                return Response({
                    'error': 'No receipt file uploaded'
                }, status=400)
            
            file = request.FILES['receipt']
            
            # Validate file
            max_size = getattr(settings, 'DOCUMENT_MAX_SIZE', 10485760)
            if file.size > max_size:
                return Response({
                    'error': f'File size exceeds {max_size / (1024*1024):.0f}MB limit'
                }, status=400)
            
            # Save file
            file_name = f'receipts/request_{request_id}_{file.name}'
            file_path = default_storage.save(file_name, file)
            full_file_path = default_storage.path(file_path)
            
            return Response({
                'success': True,
                'file_path': file_path,
                'full_path': full_file_path,
                'file_name': file.name,
                'message': 'Receipt uploaded successfully'
            })
            
        except Exception as e:
            return Response({
                'error': f'Receipt upload failed: {str(e)}'
            }, status=500)
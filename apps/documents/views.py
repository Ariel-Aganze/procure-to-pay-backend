from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.utils import timezone
import hashlib
import os
import json
import logging
import time
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
            
            # FIXED: Store upload info in cache AND session for reliability
            upload_key = f"upload_{request.user.id}_{request_id}"
            upload_info = {
                'file_path': file_path,
                'full_file_path': full_file_path,
                'file_name': file.name,
                'file_size': file.size,
                'content_type': file.content_type,
                'uploaded_at': timezone.now().isoformat(),
                'user_id': request.user.id
            }
            
            # Store in cache (24 hours) AND session
            cache.set(upload_key, upload_info, timeout=86400)  # 24 hours
            
            # Also store in session as backup
            uploaded_files = getattr(request.session, 'uploaded_files', {})
            uploaded_files[str(request_id)] = upload_info
            request.session['uploaded_files'] = uploaded_files
            request.session.modified = True
            
            return Response({
                'success': True,
                'file_path': file_path,
                'full_path': full_file_path,
                'file_name': file.name,
                'file_size': file.size,
                'content_type': file.content_type,
                'request_id': request_id,
                'upload_key': upload_key,  # Return for debugging
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
            
            # FIXED: Better file path resolution with multiple fallbacks
            full_file_path = self._get_file_path(request, request_id, file_path)
            
            if not full_file_path or not os.path.exists(full_file_path):
                return Response({
                    'error': 'Uploaded file not found. Please upload the file again.',
                    'debug_info': {
                        'requested_path': file_path,
                        'resolved_path': full_file_path,
                        'file_exists': os.path.exists(full_file_path) if full_file_path else False
                    }
                }, status=400)
                
            logger.info(f"Processing file: {full_file_path}")
            
            # FIXED: Generate more reliable job ID
            job_id = f"job_{request.user.id}_{request_id}_{document_type}_{int(time.time())}"
            
            # FIXED: Store job info in cache AND session for reliability
            job_info = {
                'status': 'queued',
                'document_type': document_type,
                'file_path': full_file_path,
                'user_id': request.user.id,
                'request_id': request_id,
                'created_at': timezone.now().isoformat(),
                'job_id': job_id
            }
            
            # Store in cache (2 hours) AND session
            job_cache_key = f"job_{job_id}"
            cache.set(job_cache_key, job_info, timeout=7200)  # 2 hours
            
            # Also store in session as backup
            processing_jobs = getattr(request.session, 'processing_jobs', {})
            processing_jobs[job_id] = job_info
            request.session['processing_jobs'] = processing_jobs
            request.session.modified = True
            
            logger.info(f"Job queued: {job_id} (stored in cache and session)")
            
            return Response({
                'success': True,
                'job_id': job_id,
                'status': 'queued',
                'message': f'{document_type} processing queued for real AI extraction',
                'estimated_time': '15-45 seconds',
                'file_path': full_file_path,
                'cache_key': job_cache_key  # Return for debugging
            })
            
        except Exception as e:
            logger.error(f"Processing setup error: {e}", exc_info=True)
            return Response({
                'error': f'Processing setup failed: {str(e)}'
            }, status=500)
    
    def _get_file_path(self, request, request_id, provided_file_path):
        """Get file path with multiple fallback methods"""
        
        # Method 1: Use provided file path
        if provided_file_path:
            if provided_file_path.startswith('/'):
                full_path = provided_file_path
            else:
                full_path = os.path.join(settings.MEDIA_ROOT, provided_file_path)
            
            if os.path.exists(full_path):
                logger.info(f"Found file using provided path: {full_path}")
                return full_path
        
        # Method 2: Check cache
        upload_key = f"upload_{request.user.id}_{request_id}"
        cached_info = cache.get(upload_key)
        if cached_info and cached_info.get('full_file_path'):
            full_path = cached_info['full_file_path']
            if os.path.exists(full_path):
                logger.info(f"Found file using cache: {full_path}")
                return full_path
        
        # Method 3: Check session
        uploaded_files = getattr(request.session, 'uploaded_files', {})
        file_info = uploaded_files.get(str(request_id))
        if file_info and file_info.get('full_file_path'):
            full_path = file_info['full_file_path']
            if os.path.exists(full_path):
                logger.info(f"Found file using session: {full_path}")
                return full_path
        
        # Method 4: Search for recent files
        try:
            import glob
            upload_pattern = os.path.join(settings.MEDIA_ROOT, 'proformas', f'request_{request_id}_*')
            recent_files = glob.glob(upload_pattern)
            
            if recent_files:
                # Get the most recent file
                full_path = max(recent_files, key=os.path.getctime)
                logger.info(f"Found file using glob search: {full_path}")
                return full_path
        except Exception as e:
            logger.warning(f"Glob search failed: {e}")
        
        logger.error(f"Could not find file for request_id: {request_id}")
        return None

class ProcessingStatusView(APIView):
    """Check real processing status and return actual results"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, request_id, job_id):
        try:
            logger.info(f"Checking status for job: {job_id}")
            
            # FIXED: Check cache first, then session
            job_info = self._get_job_info(job_id)
            
            if not job_info:
                return Response({
                    'status': 'not_found',
                    'error': 'Job not found. It may have expired or never existed.',
                    'job_id': job_id,
                    'debug_info': {
                        'cache_checked': True,
                        'session_checked': True,
                        'suggestion': 'Try uploading and processing the document again.'
                    }
                }, status=404)
            
            # Verify job belongs to current user
            if job_info.get('user_id') != request.user.id:
                return Response({
                    'status': 'access_denied',
                    'error': 'You do not have access to this job.'
                }, status=403)
            
            # Check if job is already completed
            if job_info.get('status') == 'completed':
                return Response({
                    'status': 'completed',
                    'job_id': job_id,
                    'result': job_info.get('result'),
                    'processing_time': job_info.get('processing_time', 0),
                    'ai_provider': 'Comet AI (Cohere) - Real Extraction',
                    'completed_at': job_info.get('completed_at')
                })
            
            # Check if job failed
            if job_info.get('status') == 'failed':
                return Response({
                    'status': 'failed',
                    'job_id': job_id,
                    'error': job_info.get('error', 'Unknown error'),
                    'error_data': job_info.get('error_data', {}),
                    'processing_time': job_info.get('processing_time', 0),
                    'retry_suggestion': 'Try uploading and processing the document again.'
                })
            
            # Process the document with real AI
            file_path = job_info['file_path']
            document_type = job_info['document_type']
            
            # Verify file still exists
            if not os.path.exists(file_path):
                # Update job as failed
                self._update_job_status(job_id, {
                    'status': 'failed',
                    'error': 'Source file no longer exists',
                    'processing_time': 0
                })
                
                return Response({
                    'status': 'failed',
                    'job_id': job_id,
                    'error': 'Source file no longer exists. Please upload the document again.',
                    'processing_time': 0
                })
            
            logger.info(f"Processing document: {file_path} of type: {document_type}")
            
            # Update status to processing
            self._update_job_status(job_id, {
                'status': 'processing',
                'started_at': timezone.now().isoformat()
            })
            
            # Perform real document processing
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
                    completed_job = {
                        'status': 'completed',
                        'result': processing_result['data'],
                        'processing_time': round(processing_time, 2),
                        'completed_at': timezone.now().isoformat(),
                        'ai_provider': processing_result.get('ai_provider', 'Enhanced Cohere')
                    }
                    self._update_job_status(job_id, completed_job)
                    
                    return Response({
                        'status': 'completed',
                        'job_id': job_id,
                        'result': processing_result['data'],
                        'processing_time': round(processing_time, 2),
                        'ai_provider': 'Comet AI (Cohere) - Real Extraction',
                        'completed_at': completed_job['completed_at']
                    })
                else:
                    # Processing failed
                    error_data = processing_result.get('data', {})
                    failed_job = {
                        'status': 'failed',
                        'error': processing_result.get('error', 'Unknown error'),
                        'error_data': error_data,
                        'processing_time': round(processing_time, 2)
                    }
                    self._update_job_status(job_id, failed_job)
                    
                    return Response({
                        'status': 'failed',
                        'job_id': job_id,
                        'error': processing_result.get('error'),
                        'error_data': error_data,
                        'processing_time': round(processing_time, 2),
                        'retry_suggestion': 'Check the document quality and try again.'
                    })
                    
            except Exception as processing_error:
                # Processing exception
                processing_time = time.time() - start_time
                error_message = str(processing_error)
                
                logger.error(f"Processing exception: {error_message}", exc_info=True)
                
                failed_job = {
                    'status': 'failed',
                    'error': error_message,
                    'processing_time': round(processing_time, 2)
                }
                self._update_job_status(job_id, failed_job)
                
                return Response({
                    'status': 'failed',
                    'job_id': job_id,
                    'error': f'Processing error: {error_message}',
                    'processing_time': round(processing_time, 2),
                    'retry_possible': True,
                    'retry_suggestion': 'The document may be corrupted or unreadable. Try a different file.'
                })
                
        except Exception as e:
            logger.error(f"Status check error: {e}", exc_info=True)
            return Response({
                'status': 'error',
                'error': f'Status check failed: {str(e)}',
                'suggestion': 'Please try uploading and processing the document again.'
            }, status=500)
    
    def _get_job_info(self, job_id):
        """Get job info from cache or session"""
        
        # Try cache first
        job_cache_key = f"job_{job_id}"
        job_info = cache.get(job_cache_key)
        
        if job_info:
            logger.info(f"Found job in cache: {job_id}")
            return job_info
        
        # Try session as fallback
        if hasattr(self.request, 'session'):
            processing_jobs = getattr(self.request.session, 'processing_jobs', {})
            job_info = processing_jobs.get(job_id)
            
            if job_info:
                logger.info(f"Found job in session: {job_id}")
                # Restore to cache
                cache.set(job_cache_key, job_info, timeout=7200)
                return job_info
        
        logger.warning(f"Job not found anywhere: {job_id}")
        return None
    
    def _update_job_status(self, job_id, updates):
        """Update job status in both cache and session"""
        
        # Update in cache
        job_cache_key = f"job_{job_id}"
        job_info = cache.get(job_cache_key, {})
        job_info.update(updates)
        cache.set(job_cache_key, job_info, timeout=7200)
        
        # Update in session
        if hasattr(self.request, 'session'):
            processing_jobs = getattr(self.request.session, 'processing_jobs', {})
            if job_id in processing_jobs:
                processing_jobs[job_id].update(updates)
                self.request.session['processing_jobs'] = processing_jobs
                self.request.session.modified = True

class ProcessingStatsView(APIView):
    """Get real processing statistics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get stats from session (for now)
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
            'storage_method': 'Cache + Session (Enhanced)',
            'features': [
                'PDF text extraction',
                'Image text recognition', 
                'Real AI analysis',
                'Structured data extraction',
                'Enhanced error handling',
                'Persistent job tracking'
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
            
            # Store in cache and session like proforma upload
            upload_key = f"receipt_{request.user.id}_{request_id}"
            upload_info = {
                'file_path': file_path,
                'full_file_path': full_file_path,
                'file_name': file.name,
                'file_size': file.size,
                'content_type': file.content_type,
                'uploaded_at': timezone.now().isoformat(),
                'user_id': request.user.id,
                'document_type': 'receipt'
            }
            
            cache.set(upload_key, upload_info, timeout=86400)
            
            return Response({
                'success': True,
                'file_path': file_path,
                'full_path': full_file_path,
                'file_name': file.name,
                'upload_key': upload_key,
                'message': 'Receipt uploaded successfully'
            })
            
        except Exception as e:
            return Response({
                'error': f'Receipt upload failed: {str(e)}'
            }, status=500)
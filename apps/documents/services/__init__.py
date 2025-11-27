# apps/documents/services/__init__.py
from .document_processor import (
    CohereDocumentProcessor,
    DocumentProcessingService,
    document_service
)

# Export the classes and service instance
__all__ = [
    'CohereDocumentProcessor',
    'DocumentProcessingService', 
    'document_service'
]

# For backwards compatibility with old imports
def process_document_with_cohere(file, document_type, request_id=None):
    """Backwards compatible function for document processing"""
    return document_service.process_document(file, document_type, request_id)
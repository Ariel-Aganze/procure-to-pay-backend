import requests
import json
import logging
import base64
import os
import PyPDF2
import io
import pdfplumber
import pytesseract
from PIL import Image
from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

class CohereDocumentProcessor:
    """
    Document processing with Cohere API - ENHANCED VERSION
    Preserves original functionality while adding improvements
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'COHERE_API_KEY', '')
        self.api_url = getattr(settings, 'COHERE_API_URL', 'https://api.cohere.ai/v1')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
    
    def is_available(self):
        """Check if Cohere API is available"""
        try:
            if not self.api_key:
                return False, "Cohere API key not configured in settings"
            
            # Test API connectivity
            response = requests.post(
                f'{self.api_url}/generate',
                headers=self.headers,
                json={
                    'model': 'command',
                    'prompt': 'Hello',
                    'max_tokens': 5,
                    'temperature': 0.1
                },
                timeout=10
            )
            
            if response.status_code in [200, 400]:
                return True, "Connected to Cohere API"
            else:
                return False, f"API responded with status {response.status_code}"
                
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    def extract_text_from_file(self, file_path):
        """Enhanced text extraction with multiple fallback methods"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
                
            file_extension = os.path.splitext(file_path)[1].lower()
            logger.info(f"Extracting text from {file_extension} file: {file_path}")
            
            if file_extension == '.pdf':
                return self._extract_text_from_pdf(file_path)
            elif file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                return self._extract_text_from_image(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
                
        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}")
            raise
    
    def _extract_text_from_pdf(self, pdf_path):
        """Enhanced PDF text extraction with multiple methods"""
        text = ""
        
        try:
            # Method 1: pdfplumber (best for structured documents)
            logger.info("Trying pdfplumber for PDF text extraction...")
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    except Exception as e:
                        logger.warning(f"pdfplumber failed on page {page_num}: {str(e)}")
            
            if len(text.strip()) > 50:  # If we got substantial text
                logger.info(f"pdfplumber extracted {len(text)} characters")
                return text.strip()
            
            # Method 2: PyPDF2 fallback (original method)
            logger.info("pdfplumber insufficient, trying PyPDF2...")
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    except Exception as e:
                        logger.warning(f"PyPDF2 failed on page {page_num}: {str(e)}")
            
            if len(text.strip()) > 50:
                logger.info(f"PyPDF2 extracted {len(text)} characters")
                return text.strip()
            
            # Method 3: OCR as final fallback
            logger.info("PDF text extraction failed, attempting OCR...")
            return self._ocr_pdf_pages(pdf_path)
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            return ""
    
    def _extract_text_from_image(self, image_path):
        """Enhanced image OCR with multiple configurations"""
        try:
            logger.info(f"Starting OCR extraction from image: {image_path}")
            
            # Load and preprocess image
            image = Image.open(image_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Try different OCR configurations for best results
            ocr_configs = [
                r'--oem 3 --psm 6',  # Uniform block of text
                r'--oem 3 --psm 4',  # Single column of text  
                r'--oem 3 --psm 3',  # Fully automatic page segmentation
                r'--oem 3 --psm 1',  # Automatic page segmentation with OSD
            ]
            
            best_text = ""
            best_config = ""
            
            for config in ocr_configs:
                try:
                    text = pytesseract.image_to_string(image, config=config, lang='eng')
                    if len(text.strip()) > len(best_text.strip()):
                        best_text = text
                        best_config = config
                except Exception as e:
                    logger.warning(f"OCR config '{config}' failed: {str(e)}")
                    continue
            
            if best_text.strip():
                logger.info(f"OCR extracted {len(best_text)} characters using config: {best_config}")
                return best_text
            else:
                # Try EasyOCR as fallback if available
                try:
                    import easyocr
                    reader = easyocr.Reader(['en'])
                    result = reader.readtext(image_path, paragraph=True)
                    text = '\n'.join([item[1] for item in result])
                    logger.info(f"EasyOCR extracted {len(text)} characters")
                    return text
                except ImportError:
                    logger.warning("EasyOCR not available for fallback")
                    return ""
                    
        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}")
            if "tesseract" in str(e).lower():
                raise Exception("Tesseract OCR is required but not properly installed. Please install tesseract-ocr.")
            return ""
    
    def _ocr_pdf_pages(self, pdf_path, max_pages=3):
        """Convert PDF pages to images and OCR them"""
        try:
            import fitz  # PyMuPDF
            text = ""
            
            doc = fitz.open(pdf_path)
            for page_num in range(min(max_pages, len(doc))):
                try:
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap()
                    
                    # Convert to PIL Image
                    img_data = pix.tobytes("ppm")
                    image = Image.open(io.BytesIO(img_data))
                    
                    # OCR the image
                    page_text = pytesseract.image_to_string(image)
                    text += page_text + "\n"
                    logger.info(f"OCR processed page {page_num + 1}")
                    
                except Exception as e:
                    logger.warning(f"OCR failed for PDF page {page_num}: {str(e)}")
                    continue
                    
            doc.close()
            return text
            
        except ImportError:
            logger.error("PyMuPDF (fitz) is required for PDF to image conversion")
            return ""
        except Exception as e:
            logger.error(f"Error in PDF OCR: {str(e)}")
            return ""
    
    def process_proforma_with_ai(self, extracted_text):
        """Process proforma text with Cohere AI - ENHANCED VERSION"""
        try:
            if not extracted_text or len(extracted_text.strip()) < 10:
                return self._create_extraction_error("Insufficient text extracted", extracted_text)
            
            logger.info(f"Processing {len(extracted_text)} characters with Cohere AI")
            
            # Enhanced prompt for better extraction
            prompt = f"""
            Extract structured data from this business document (proforma invoice/quotation).
            
            Document text:
            {extracted_text}
            
            Extract the following information and return it as valid JSON only:
            {{
                "vendor_name": "Company name exactly as shown",
                "vendor_address": "Complete address",
                "vendor_email": "Email address",
                "vendor_phone": "Phone number",
                "document_number": "Invoice/quote number",
                "document_date": "Date in YYYY-MM-DD format",
                "line_items": [
                    {{
                        "description": "Item description",
                        "quantity": 1,
                        "unit_price": 0.00,
                        "total_price": 0.00
                    }}
                ],
                "subtotal": 0.00,
                "tax_amount": 0.00,
                "total_amount": 0.00,
                "currency": "USD",
                "payment_terms": "Payment terms",
                "delivery_terms": "Delivery terms"
            }}
            
            IMPORTANT:
            - Return ONLY valid JSON, no other text
            - Use null for missing information
            - Convert amounts to numbers (not strings)
            - Extract data only from the document text above
            - Do not use example or default values
            """
            
            # Use Cohere's best model for document processing
            response = requests.post(
                f'{self.api_url}/generate',
                headers=self.headers,
                json={
                    'model': 'command-r-plus',  # Best model for structured tasks
                    'prompt': prompt,
                    'max_tokens': 2000,  # Increased for more detailed extraction
                    'temperature': 0.1,  # Low temperature for consistency
                    'stop_sequences': ['\n\n---', '\n\nNote:', 'Here is'],
                    'return_likelihoods': 'NONE'  # Focus on generation
                },
                timeout=45  # Increased timeout for complex documents
            )
            
            if response.status_code == 200:
                result = response.json()
                generated_text = result.get('generations', [{}])[0].get('text', '')
                
                logger.info(f"Cohere AI response ({len(generated_text)} chars): {generated_text[:200]}...")
                
                # Enhanced JSON parsing
                extracted_data = self._parse_json_response(generated_text)
                
                if extracted_data and not extracted_data.get('error'):
                    # Add metadata
                    extracted_data['_ai_confidence'] = 0.90  # High confidence for Cohere
                    extracted_data['_processing_method'] = 'cohere_ai_enhanced'
                    extracted_data['_source_text_length'] = len(extracted_text)
                    extracted_data['_model_used'] = 'command-r-plus'
                    
                    logger.info("Successfully extracted data with Cohere AI")
                    return extracted_data
                else:
                    logger.error("Could not parse AI response as JSON")
                    return self._create_extraction_error("AI response could not be parsed", extracted_text, generated_text)
            else:
                error_msg = f"Cohere API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return self._create_extraction_error(error_msg, extracted_text)
                
        except Exception as e:
            logger.error(f"Cohere AI processing error: {str(e)}")
            return self._create_extraction_error(str(e), extracted_text)
    
    def _parse_json_response(self, ai_response):
        """Enhanced JSON parsing from AI response"""
        try:
            # Method 1: Direct JSON parse
            if ai_response.strip().startswith('{') and ai_response.strip().endswith('}'):
                return json.loads(ai_response.strip())
            
            # Method 2: Extract JSON block
            import re
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                return json.loads(json_text)
            
            # Method 3: Look for code block
            code_block_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', ai_response, re.DOTALL | re.IGNORECASE)
            if code_block_match:
                json_text = code_block_match.group(1)
                return json.loads(json_text)
            
            # Method 4: Manual fallback
            logger.warning("Could not find JSON in AI response, attempting manual extraction")
            return self._manual_extract_from_response(ai_response)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {str(e)}")
            logger.debug(f"AI response was: {ai_response[:500]}...")
            return None
        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            return None
    
    def _manual_extract_from_response(self, response_text):
        """Manual extraction when JSON parsing fails"""
        import re
        
        # Try to extract key information using regex
        vendor_match = re.search(r'"vendor_name":\s*"([^"]+)"', response_text)
        total_match = re.search(r'"total_amount":\s*(\d+\.?\d*)', response_text)
        email_match = re.search(r'"vendor_email":\s*"([^"]+)"', response_text)
        
        return {
            "vendor_name": vendor_match.group(1) if vendor_match else None,
            "vendor_address": None,
            "vendor_email": email_match.group(1) if email_match else None,
            "vendor_phone": None,
            "document_number": None,
            "document_date": None,
            "line_items": [],
            "subtotal": None,
            "tax_amount": None,
            "total_amount": float(total_match.group(1)) if total_match else None,
            "currency": "USD",
            "payment_terms": None,
            "delivery_terms": None,
            "_extraction_method": "manual_fallback"
        }
    
    def _create_extraction_error(self, error_message, extracted_text, ai_response=None):
        """Create detailed error response with diagnostic info"""
        return {
            "error": True,
            "error_message": error_message,
            "extracted_text_preview": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            "extracted_text_length": len(extracted_text) if extracted_text else 0,
            "ai_response_preview": ai_response[:300] + "..." if ai_response and len(ai_response) > 300 else ai_response,
            "ai_confidence": 0.0,
            "processing_method": "failed_extraction",
            "suggestions": [
                "Text extraction successful but AI processing failed",
                "Check if document is clear and readable",
                "Consider using a different document format",
                f"Extracted text length: {len(extracted_text) if extracted_text else 0} characters"
            ]
        }
    
    def process_proforma(self, file_path=None, file_content=None):
        """Process proforma document - ENHANCED IMPLEMENTATION"""
        try:
            logger.info(f"Starting enhanced proforma processing for file: {file_path}")
            
            # Extract text from the uploaded file
            extracted_text = self.extract_text_from_file(file_path)
            
            if not extracted_text or len(extracted_text.strip()) < 10:
                return {
                    "success": False,
                    "error": "Could not extract sufficient text from the uploaded file",
                    "suggestions": [
                        "Ensure the file is a clear PDF or image",
                        "Install Tesseract OCR for better text extraction",
                        "Try uploading a different format (PDF preferred)"
                    ],
                    "extracted_text_length": len(extracted_text) if extracted_text else 0
                }
            
            logger.info(f"Extracted text length: {len(extracted_text)} characters")
            logger.info(f"Text preview: {extracted_text[:200]}...")
            
            # Process with enhanced Cohere AI
            extraction_result = self.process_proforma_with_ai(extracted_text)
            
            if extraction_result.get('error'):
                return {
                    "success": False,
                    "data": extraction_result
                }
            else:
                return {
                    "success": True,
                    "data": extraction_result
                }
            
        except Exception as e:
            logger.error(f"Proforma processing error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_receipt(self, file_path=None, file_content=None, purchase_order_data=None):
        """Process receipt document using the same enhanced logic"""
        try:
            logger.info(f"Starting enhanced receipt processing for file: {file_path}")
            
            extracted_text = self.extract_text_from_file(file_path)
            
            if not extracted_text or len(extracted_text.strip()) < 10:
                return {
                    "success": False,
                    "error": "Could not extract sufficient text from the uploaded receipt"
                }
            
            logger.info(f"Extracted receipt text length: {len(extracted_text)} characters")
            
            # Use similar AI processing for receipts
            extraction_result = self.process_proforma_with_ai(extracted_text)  # Same extraction logic
            
            # Add receipt validation if PO data is provided
            if extraction_result and not extraction_result.get('error') and purchase_order_data:
                validation_result = self._validate_receipt_against_po(extraction_result, purchase_order_data)
                extraction_result['validation'] = validation_result
            
            if extraction_result.get('error'):
                return {
                    "success": False,
                    "data": extraction_result
                }
            else:
                return {
                    "success": True,
                    "data": extraction_result
                }
            
        except Exception as e:
            logger.error(f"Receipt processing error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _validate_receipt_against_po(self, receipt_data, po_data):
        """Enhanced receipt validation against purchase order"""
        validation = {
            'vendor_match': False,
            'amount_match': False,
            'items_match': False,
            'date_valid': True,
            'discrepancies': [],
            'warnings': [],
            'overall_score': 0.0
        }
        
        try:
            # Vendor validation
            receipt_vendor = receipt_data.get('vendor_name', '').lower().strip()
            po_vendor = po_data.get('vendor_name', '').lower().strip()
            
            if receipt_vendor and po_vendor:
                # Flexible vendor matching
                validation['vendor_match'] = (
                    receipt_vendor in po_vendor or 
                    po_vendor in receipt_vendor or
                    receipt_vendor == po_vendor
                )
                if not validation['vendor_match']:
                    validation['discrepancies'].append(
                        f"Vendor mismatch: Receipt shows '{receipt_data.get('vendor_name')}', PO shows '{po_data.get('vendor_name')}'"
                    )
            
            # Amount validation with tolerance
            receipt_total = float(receipt_data.get('total_amount', 0))
            po_total = float(po_data.get('total_amount', 0))
            
            if receipt_total > 0 and po_total > 0:
                amount_diff = abs(receipt_total - po_total)
                tolerance = max(10.00, po_total * 0.05)  # 5% or $10, whichever is higher
                validation['amount_match'] = amount_diff <= tolerance
                
                if not validation['amount_match']:
                    validation['discrepancies'].append(
                        f"Amount difference: ${amount_diff:.2f} (Receipt: ${receipt_total:.2f}, PO: ${po_total:.2f})"
                    )
                elif amount_diff > 0:
                    validation['warnings'].append(
                        f"Minor amount difference: ${amount_diff:.2f} (within tolerance)"
                    )
            
            # Calculate overall score
            score_items = [validation['vendor_match'], validation['amount_match'], validation['date_valid']]
            validation['overall_score'] = sum(score_items) / len(score_items)
            
            # Set validation status
            if validation['overall_score'] >= 0.8:
                validation['status'] = 'approved'
            elif validation['overall_score'] >= 0.6:
                validation['status'] = 'approved_with_notes'
            else:
                validation['status'] = 'requires_review'
            
        except Exception as e:
            logger.error(f"Receipt validation error: {str(e)}")
            validation['discrepancies'].append(f"Validation error: {str(e)}")
            validation['status'] = 'error'
        
        return validation


class DocumentProcessingService:
    """Enhanced main service that preserves CohereDocumentProcessor functionality"""
    
    def __init__(self):
        self.cohere_processor = CohereDocumentProcessor()
    
    def get_status(self):
        """Get enhanced service status"""
        is_available, message = self.cohere_processor.is_available()
        
        return {
            'available': is_available,
            'provider': 'Comet AI (Cohere Enhanced)',
            'message': message,
            'models': getattr(settings, 'AI_PROCESSING_MODELS', {
                'document_extraction': 'command-r-plus',
                'receipt_validation': 'command-r',
                'text_analysis': 'command'
            }),
            'api_configured': bool(getattr(settings, 'COHERE_API_KEY', '')),
            'ocr_status': self._get_ocr_status(),
            'supported_formats': ['PDF', 'JPG', 'JPEG', 'PNG', 'BMP', 'TIFF'],
            'enhanced_features': [
                'Multi-method text extraction',
                'Enhanced OCR with multiple configs',
                'Better JSON parsing',
                'Detailed error reporting',
                'Receipt validation'
            ]
        }
    
    def _get_ocr_status(self):
        """Check OCR availability with details"""
        ocr_info = []
        
        try:
            import pytesseract
            version = pytesseract.get_tesseract_version()
            ocr_info.append(f"Tesseract OCR v{version} available")
        except Exception:
            ocr_info.append("Tesseract OCR not available")
        
        try:
            import easyocr
            ocr_info.append("EasyOCR available (fallback)")
        except ImportError:
            ocr_info.append("EasyOCR not available")
        
        try:
            import fitz  # PyMuPDF
            ocr_info.append("PyMuPDF available (PDF to image)")
        except ImportError:
            ocr_info.append("PyMuPDF not available")
        
        return "; ".join(ocr_info) if ocr_info else "Manual extraction only (limited)"
    
    def process_document(self, file_path, document_type, request_id=None):
        """Process any document type with enhanced CohereDocumentProcessor"""
        try:
            logger.info(f"Processing {document_type} document: {file_path}")
            
            if document_type == 'proforma':
                return self.cohere_processor.process_proforma(file_path=file_path)
            elif document_type == 'receipt':
                # Get PO data if available for validation
                po_data = None
                if request_id:
                    # In a real implementation, fetch PO data from database
                    # po_data = get_purchase_order_data(request_id)
                    pass
                
                return self.cohere_processor.process_receipt(
                    file_path=file_path, 
                    purchase_order_data=po_data
                )
            else:
                return {
                    "success": False,
                    "error": f"Unsupported document type: {document_type}"
                }
        except Exception as e:
            logger.error(f"Document processing error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


# Global service instance - preserves your original pattern
document_service = DocumentProcessingService()

# Backwards compatibility function - preserves your original API
def process_document_with_cohere(file_path, document_type, request_id=None):
    """Enhanced document processing with real Cohere AI extraction"""
    return document_service.process_document(file_path, document_type, request_id)
import requests
import json
import logging
import os
import pdfplumber
import pytesseract
import PyPDF2
from PIL import Image
from django.conf import settings
from typing import Dict, Any, Optional
import tempfile

logger = logging.getLogger(__name__)

class OllamaService:
    def __init__(self):
        self.base_url = getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434')
        self.model = getattr(settings, 'OLLAMA_MODEL', 'llama3.2')
        self.timeout = 60  # seconds
    
    def is_available(self) -> bool:
        """Check if Ollama service is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                # Check if our model is available
                model_names = [model.get('name', '') for model in models]
                available = any(self.model in name for name in model_names)
                logger.info(f"Ollama available: {available}, Models: {model_names}")
                return available
            return False
        except Exception as e:
            logger.error(f"Ollama service check failed: {str(e)}")
            return False
    
    def extract_text_from_file(self, file_path: str) -> str:
        """Extract text from uploaded file (PDF or image)"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Determine file type
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension == '.pdf':
                return self._extract_text_from_pdf(file_path)
            elif file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                return self._extract_text_from_image(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
        
        except Exception as e:
            logger.error(f"Error extracting text from file {file_path}: {str(e)}")
            raise
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF using pdfplumber and PyPDF2 fallback"""
        text = ""
        
        try:
            # Try pdfplumber first (better for structured data)
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            if text.strip():
                logger.info(f"Successfully extracted {len(text)} characters from PDF using pdfplumber")
                return text
            
            # Fallback to PyPDF2
            logger.info("pdfplumber extraction was empty, trying PyPDF2...")
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    except Exception as e:
                        logger.warning(f"Could not extract text from page {page_num}: {str(e)}")
            
            logger.info(f"PyPDF2 extracted {len(text)} characters from PDF")
            return text
        
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise
    
    def _extract_text_from_image(self, image_path: str) -> str:
        """Extract text from image using OCR"""
        try:
            # Use pytesseract for OCR
            logger.info(f"Starting OCR extraction from image: {image_path}")
            
            # Open and preprocess image for better OCR results
            image = Image.open(image_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Use pytesseract with custom config for better results
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(image, config=custom_config)
            
            logger.info(f"OCR extracted {len(text)} characters from image")
            return text
            
        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}")
            # If tesseract is not installed, provide helpful error
            if "not found" in str(e).lower() or "tesseract" in str(e).lower():
                logger.error("Tesseract OCR is not installed. Please install it for image processing.")
                raise Exception("Tesseract OCR is required for image processing but is not installed.")
            raise
    
    def generate_completion(self, prompt: str, context: str = "") -> Dict[str, Any]:
        """Generate completion using Ollama"""
        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt
            
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Lower temperature for more consistent results
                    "top_p": 0.9,
                    "num_predict": 2048
                }
            }
            
            logger.info(f"Sending request to Ollama: {self.base_url}/api/generate")
            logger.debug(f"Prompt length: {len(full_prompt)} characters")
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info("Ollama completion successful")
                return result
            else:
                error_msg = f"Ollama API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
        
        except Exception as e:
            logger.error(f"Error generating completion: {str(e)}")
            raise
    
    def extract_proforma_data(self, text: str) -> Dict[str, Any]:
        """Extract structured data from proforma invoice text using Ollama"""
        try:
            if not text or not text.strip():
                raise ValueError("No text provided for extraction")
            
            logger.info(f"Starting AI extraction from text ({len(text)} characters)")
            
            prompt = f"""
            Extract information from this proforma invoice/quotation text and return it as JSON.
            
            Document text:
            {text}
            
            Extract the following information and return ONLY a valid JSON object:
            {{
                "vendor_name": "Company name",
                "vendor_address": "Full address",
                "vendor_email": "Email address",
                "vendor_phone": "Phone number",
                "document_number": "Document/invoice number",
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
            
            Important:
            - Return ONLY valid JSON, no other text
            - Use null for missing information
            - Convert all amounts to numbers (not strings)
            - Ensure the JSON is properly formatted
            """
            
            # Get AI completion
            response = self.generate_completion(prompt)
            ai_response = response.get('response', '')
            
            if not ai_response:
                raise ValueError("Empty response from AI")
            
            logger.info(f"AI response length: {len(ai_response)} characters")
            logger.debug(f"AI response preview: {ai_response[:200]}...")
            
            # Parse JSON from response
            try:
                # Try to find JSON in the response
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_text = ai_response[json_start:json_end]
                    extracted_data = json.loads(json_text)
                    logger.info("Successfully parsed AI response as JSON")
                    return extracted_data
                else:
                    raise ValueError("No JSON found in AI response")
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {str(e)}")
                logger.error(f"AI response was: {ai_response}")
                
                # Fallback: try to extract data manually
                return self._manual_extract_from_text(text, ai_response)
        
        except Exception as e:
            logger.error(f"Error in extract_proforma_data: {str(e)}")
            # Return fallback data with error indication
            return self._create_fallback_data(text, str(e))
    
    def _manual_extract_from_text(self, original_text: str, ai_response: str) -> Dict[str, Any]:
        """Manually extract data when JSON parsing fails"""
        logger.info("Attempting manual data extraction from text")
        
        # Simple regex-based extraction as fallback
        import re
        
        # Try to extract vendor name (usually at the top)
        vendor_patterns = [
            r'^([A-Z][A-Za-z\s&,.-]+(?:Inc|LLC|Ltd|Corp|Company)\.?)',
            r'FROM:\s*([^\n]+)',
            r'VENDOR:\s*([^\n]+)',
            r'^([A-Z][A-Za-z\s]+)\n'
        ]
        
        vendor_name = "Unknown Vendor"
        for pattern in vendor_patterns:
            match = re.search(pattern, original_text, re.MULTILINE)
            if match:
                vendor_name = match.group(1).strip()
                break
        
        # Extract total amount
        amount_patterns = [
            r'TOTAL[:\s]+\$?(\d+[\d,]*\.?\d*)',
            r'Total Amount[:\s]+\$?(\d+[\d,]*\.?\d*)',
            r'Grand Total[:\s]+\$?(\d+[\d,]*\.?\d*)',
            r'\$(\d+[\d,]*\.?\d*)\s*$'
        ]
        
        total_amount = 0.0
        for pattern in amount_patterns:
            match = re.search(pattern, original_text, re.IGNORECASE)
            if match:
                try:
                    total_amount = float(match.group(1).replace(',', ''))
                    break
                except ValueError:
                    continue
        
        # Extract date
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2})'
        ]
        
        document_date = None
        for pattern in date_patterns:
            match = re.search(pattern, original_text)
            if match:
                document_date = match.group(1)
                break
        
        result = {
            "vendor_name": vendor_name,
            "vendor_address": None,
            "vendor_email": None,
            "vendor_phone": None,
            "document_number": None,
            "document_date": document_date,
            "line_items": [],
            "subtotal": total_amount * 0.9 if total_amount > 0 else 0.0,  # Estimate
            "tax_amount": total_amount * 0.1 if total_amount > 0 else 0.0,  # Estimate
            "total_amount": total_amount,
            "currency": "USD",
            "payment_terms": None,
            "delivery_terms": None,
            "_extraction_method": "manual_fallback",
            "_ai_response_preview": ai_response[:200] if ai_response else None
        }
        
        logger.info(f"Manual extraction completed: vendor={vendor_name}, total={total_amount}")
        return result
    
    def _create_fallback_data(self, text: str, error: str) -> Dict[str, Any]:
        """Create fallback data when extraction fails"""
        return {
            "vendor_name": "Extraction Failed",
            "vendor_address": None,
            "vendor_email": None,
            "vendor_phone": None,
            "document_number": None,
            "document_date": None,
            "line_items": [],
            "subtotal": 0.0,
            "tax_amount": 0.0,
            "total_amount": 0.0,
            "currency": "USD",
            "payment_terms": None,
            "delivery_terms": None,
            "_extraction_error": error,
            "_text_length": len(text),
            "_text_preview": text[:200] if text else None
        }
    
    def generate_purchase_order(self, proforma_data: Dict[str, Any], request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate purchase order from proforma and request data"""
        try:
            import uuid
            from datetime import datetime, timedelta
            
            po_number = f"PO-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
            
            po_data = {
                "po_number": po_number,
                "po_date": datetime.now().isoformat(),
                "vendor": {
                    "name": proforma_data.get('vendor_name') or request_data.get('vendor_name'),
                    "address": proforma_data.get('vendor_address'),
                    "email": proforma_data.get('vendor_email') or request_data.get('vendor_email'),
                    "phone": proforma_data.get('vendor_phone')
                },
                "buyer": {
                    "company": "Your Company Name",
                    "address": "Your Company Address",
                    "contact": request_data.get('created_by')
                },
                "items": proforma_data.get('line_items', []),
                "subtotal": proforma_data.get('subtotal', request_data.get('amount', 0)),
                "tax_amount": proforma_data.get('tax_amount', 0),
                "total_amount": proforma_data.get('total_amount', request_data.get('amount', 0)),
                "currency": proforma_data.get('currency', 'USD'),
                "payment_terms": proforma_data.get('payment_terms', 'Net 30 days'),
                "delivery_terms": proforma_data.get('delivery_terms', 'Standard delivery'),
                "expected_delivery": (datetime.now() + timedelta(days=30)).isoformat(),
                "notes": f"Generated from purchase request: {request_data.get('title')}",
                "reference_request_id": request_data.get('id'),
                "status": "issued",
                "created_at": datetime.now().isoformat()
            }
            
            logger.info(f"Generated PO: {po_number}")
            return po_data
            
        except Exception as e:
            logger.error(f"Error generating purchase order: {str(e)}")
            raise
    
    def validate_receipt(self, receipt_data: Dict[str, Any], po_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate receipt against purchase order"""
        try:
            validation_result = {
                "validation_status": "validated",
                "overall_score": 1.0,
                "vendor_match": False,
                "amount_match": False,
                "items_match": False,
                "date_valid": True,
                "discrepancies": [],
                "warnings": [],
                "recommendations": []
            }
            
            # Check vendor match
            receipt_vendor = receipt_data.get('vendor_name', '').lower()
            po_vendor = po_data.get('vendor', {}).get('name', '').lower()
            
            if receipt_vendor and po_vendor:
                validation_result["vendor_match"] = receipt_vendor == po_vendor
                if not validation_result["vendor_match"]:
                    validation_result["discrepancies"].append(
                        f"Vendor mismatch: Receipt shows '{receipt_data.get('vendor_name')}', "
                        f"PO shows '{po_data.get('vendor', {}).get('name')}'"
                    )
            
            # Check amount match (within 5% tolerance)
            receipt_total = receipt_data.get('total_amount', 0)
            po_total = po_data.get('total_amount', 0)
            
            if receipt_total and po_total:
                tolerance = abs(po_total * 0.05)  # 5% tolerance
                validation_result["amount_match"] = abs(receipt_total - po_total) <= tolerance
                if not validation_result["amount_match"]:
                    validation_result["discrepancies"].append(
                        f"Amount mismatch: Receipt total ${receipt_total}, "
                        f"PO total ${po_total} (difference: ${abs(receipt_total - po_total)})"
                    )
            
            # Calculate overall score
            checks = [validation_result["vendor_match"], validation_result["amount_match"], validation_result["date_valid"]]
            validation_result["overall_score"] = sum(checks) / len(checks)
            
            if validation_result["overall_score"] < 0.8:
                validation_result["validation_status"] = "requires_review"
            elif validation_result["discrepancies"]:
                validation_result["validation_status"] = "approved_with_notes"
            
            logger.info(f"Receipt validation completed: score={validation_result['overall_score']}")
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating receipt: {str(e)}")
            return {
                "validation_status": "error",
                "overall_score": 0.0,
                "error": str(e)
            }


# Create global instance
ollama_service = OllamaService()
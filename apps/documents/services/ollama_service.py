import requests
import json
import time
import PyPDF2
import pdfplumber
from PIL import Image
import pytesseract
from io import BytesIO
from django.conf import settings
from typing import Dict, Any, List, Optional
import logging
import mimetypes
import os

logger = logging.getLogger(__name__)


class OllamaService:
    """
    Service for interacting with Ollama AI for document processing
    Windows-compatible version without python-magic
    """
    
    def __init__(self):
        self.base_url = getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434')
        self.model = getattr(settings, 'OLLAMA_MODEL', 'llama2')
        self.timeout = 300  # 5 minutes timeout
    
    def is_available(self) -> bool:
        """Check if Ollama service is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def _get_file_type(self, file_path: str) -> str:
        """Get file type using mimetypes (Windows compatible)"""
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            return mime_type
        
        # Fallback based on file extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            return 'application/pdf'
        elif ext in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        elif ext == '.png':
            return 'image/png'
        elif ext == '.gif':
            return 'image/gif'
        else:
            return 'application/octet-stream'
    
    def extract_text_from_file(self, file_path: str) -> str:
        """Extract text from various file formats"""
        try:
            # Detect file type
            file_type = self._get_file_type(file_path)
            
            if file_type == 'application/pdf':
                return self._extract_text_from_pdf(file_path)
            elif file_type.startswith('image/'):
                return self._extract_text_from_image(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {str(e)}")
            raise
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF using multiple methods"""
        text = ""
        
        try:
            # Try pdfplumber first (better for structured data)
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            if text.strip():
                return text
            
            # Fallback to PyPDF2
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            
            return text
        
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise
    
    def _extract_text_from_image(self, image_path: str) -> str:
        """Extract text from image using OCR"""
        try:
            # Use pytesseract for OCR
            text = pytesseract.image_to_string(Image.open(image_path))
            return text
        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}")
            # If tesseract is not installed, return empty string for now
            logger.warning("Tesseract OCR not available. Install it for image processing.")
            return ""
    
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
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
        
        except Exception as e:
            logger.error(f"Error generating completion: {str(e)}")
            raise
    
    def extract_proforma_data(self, text: str) -> Dict[str, Any]:
        """Extract structured data from proforma invoice text"""
        prompt = """
        Extract information from this proforma invoice/quotation text. Return the data in JSON format with these fields:
        
        {
          "vendor_name": "Company name",
          "vendor_address": "Full address",
          "vendor_email": "Email address",
          "vendor_phone": "Phone number",
          "document_number": "Quote/Proforma number",
          "document_date": "Date (YYYY-MM-DD format)",
          "currency": "Currency code (USD, EUR, etc.)",
          "line_items": [
            {
              "description": "Item description",
              "quantity": number,
              "unit_price": number,
              "total_price": number,
              "unit": "Unit of measure"
            }
          ],
          "subtotal": number,
          "tax_amount": number,
          "total_amount": number,
          "payment_terms": "Payment terms",
          "delivery_terms": "Delivery terms",
          "validity": "Quote validity period"
        }
        
        Extract only the information that is clearly present in the text. Use null for missing fields.
        Respond with ONLY the JSON object, no additional text.
        """
        
        try:
            result = self.generate_completion(prompt, text)
            response_text = result.get('response', '').strip()
            
            # Try to parse JSON from response
            # Sometimes the model includes extra text, so we need to extract just the JSON
            if response_text.startswith('{'):
                json_end = response_text.rfind('}') + 1
                json_text = response_text[:json_end]
            else:
                # Look for JSON within the response
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start >= 0 and end > start:
                    json_text = response_text[start:end]
                else:
                    raise ValueError("No valid JSON found in response")
            
            extracted_data = json.loads(json_text)
            return extracted_data
        
        except Exception as e:
            logger.error(f"Error extracting proforma data: {str(e)}")
            raise
    
    def generate_purchase_order(self, proforma_data: Dict[str, Any], request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate purchase order content based on proforma and request data"""
        prompt = f"""
        Generate a professional purchase order based on this proforma data and purchase request information.
        
        Proforma Data:
        {json.dumps(proforma_data, indent=2)}
        
        Purchase Request:
        {json.dumps(request_data, indent=2)}
        
        Generate a purchase order with these details:
        {{
          "po_number": "PO-YYYY-XXXX format",
          "po_date": "Today's date (YYYY-MM-DD)",
          "delivery_date": "Expected delivery date",
          "buyer_info": {{
            "company": "Your Company Name",
            "address": "Your Company Address",
            "contact": "Contact person",
            "email": "contact@company.com"
          }},
          "vendor_info": "Vendor information from proforma",
          "line_items": "Items from proforma with PO formatting",
          "terms_and_conditions": [
            "Payment terms",
            "Delivery terms", 
            "Quality requirements",
            "Return policy"
          ],
          "total_amount": "Total amount",
          "currency": "Currency",
          "notes": "Any special instructions"
        }}
        
        Respond with ONLY the JSON object, no additional text.
        """
        
        try:
            result = self.generate_completion(prompt)
            response_text = result.get('response', '').strip()
            
            # Extract JSON from response
            if response_text.startswith('{'):
                json_end = response_text.rfind('}') + 1
                json_text = response_text[:json_end]
            else:
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start >= 0 and end > start:
                    json_text = response_text[start:end]
                else:
                    raise ValueError("No valid JSON found in response")
            
            po_data = json.loads(json_text)
            return po_data
        
        except Exception as e:
            logger.error(f"Error generating purchase order: {str(e)}")
            raise
    
    def validate_receipt(self, receipt_data: Dict[str, Any], po_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate receipt against purchase order"""
        prompt = f"""
        Compare this receipt data with the purchase order and identify any discrepancies.
        
        Receipt Data:
        {json.dumps(receipt_data, indent=2)}
        
        Purchase Order Data:
        {json.dumps(po_data, indent=2)}
        
        Analyze and return validation results in this format:
        {{
          "validation_status": "passed/failed/warning/requires_review",
          "overall_score": 0.95,
          "vendor_match": true,
          "amount_match": true,
          "items_match": true,
          "date_valid": true,
          "discrepancies": [
            {{
              "field": "field_name",
              "expected": "expected_value",
              "actual": "actual_value",
              "severity": "low/medium/high"
            }}
          ],
          "warnings": [
            "List of warnings"
          ],
          "recommendations": [
            "List of recommendations"
          ]
        }}
        
        Check for:
        - Vendor name and details match
        - Item descriptions and quantities match
        - Prices are within acceptable range (±5%)
        - Dates are valid and logical
        - Total amounts match
        
        Respond with ONLY the JSON object, no additional text.
        """
        
        try:
            result = self.generate_completion(prompt)
            response_text = result.get('response', '').strip()
            
            # Extract JSON from response
            if response_text.startswith('{'):
                json_end = response_text.rfind('}') + 1
                json_text = response_text[:json_end]
            else:
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start >= 0 and end > start:
                    json_text = response_text[start:end]
                else:
                    raise ValueError("No valid JSON found in response")
            
            validation_result = json.loads(json_text)
            return validation_result
        
        except Exception as e:
            logger.error(f"Error validating receipt: {str(e)}")
            raise


# Singleton instance
ollama_service = OllamaService()
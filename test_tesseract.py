from PIL import Image, ImageDraw
import pytesseract

# Explicitly tell pytesseract where tesseract.exe is
pytesseract.pytesseract.tesseract_cmd = r"C:\ProgramData\chocolatey\bin\tesseract.exe"

# Create a sample image
img = Image.new('RGB', (200, 60), color=(73, 109, 137))
d = ImageDraw.Draw(img)
d.text((10, 10), "Hello World", fill=(255, 255, 0))

# OCR
text = pytesseract.image_to_string(img)
print("Detected text:", text)

import pytesseract
from PIL import Image
import PyPDF2
import io
import re
from langdetect import detect
import magic
import os

# Set TESSDATA_PREFIX for OCR languages
os.environ['TESSDATA_PREFIX'] = '/opt/homebrew/share/'

class DocumentProcessor:
    def __init__(self):
        # Financial keywords in multiple languages
        self.financial_keywords = {
            'ru': [
                'квитанция', 'чек', 'счет', 'оплата', 'платеж', 'сумма', 
                'итого', 'к доплате', 'банк', 'карта', 'наличные',
                'услуги', 'товары', 'покупка', 'руб', 'рубл'
            ],
            'en': [
                'receipt', 'invoice', 'bill', 'payment', 'total', 'amount',
                'purchase', 'transaction', 'card', 'cash', 'bank', 'due',
                'subtotal', 'tax', 'service', 'goods'
            ],
            'de': [
                'rechnung', 'quittung', 'zahlung', 'summe', 'gesamt',
                'betrag', 'kauf', 'bank', 'karte', 'bar'
            ],
            'fr': [
                'facture', 'reçu', 'paiement', 'total', 'montant',
                'achat', 'banque', 'carte', 'espèces'
            ]
        }
        
        # Patterns for amounts (various currencies)
        self.amount_patterns = [
            r'\d+[.,]\d{2}\s*(?:руб|₽|rub)',  # Russian rubles
            r'\$\s*\d+[.,]\d{2}',              # USD
            r'€\s*\d+[.,]\d{2}',               # EUR  
            r'£\s*\d+[.,]\d{2}',               # GBP
            r'\d+[.,]\d{2}\s*(?:USD|EUR|GBP)',
            r'(?:итого|total|sum|amount)[\s:]*\d+[.,]\d{2}'
        ]
    
    def process_attachment(self, file_data, filename, mime_type):
        """Process attachment and extract financial information"""
        try:
            text = self._extract_text(file_data, mime_type)
            if not text:
                return None
            
            # Analyze text for financial content
            analysis = self._analyze_financial_content(text)
            
            if analysis['is_financial']:
                return {
                    'filename': filename,
                    'mime_type': mime_type,
                    'text': text[:1000],  # First 1000 chars
                    'language': analysis['language'],
                    'financial_score': analysis['score'],
                    'amounts_found': analysis['amounts'],
                    'keywords_found': analysis['keywords']
                }
            
            return None
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            return None
    
    def analyze_email_content(self, email_body, subject=""):
        """Analyze email body for financial content without attachments"""
        try:
            # Combine subject and body for analysis
            full_text = f"{subject}\n{email_body}"
            
            if not full_text.strip():
                return None
            
            # Analyze text for financial content
            analysis = self._analyze_financial_content(full_text)
            
            # Also look for financial links and patterns
            financial_links = self._extract_financial_links(email_body)
            if financial_links:
                analysis['score'] += len(financial_links) * 3  # Boost score for links
                analysis['keywords'].extend([f"link:{link[:30]}..." for link in financial_links[:3]])
            
            if analysis['is_financial']:
                return {
                    'filename': 'email_content',
                    'mime_type': 'text/html',
                    'text': full_text[:1000],  # First 1000 chars
                    'language': analysis['language'],
                    'financial_score': min(analysis['score'], 100),  # Cap at 100
                    'amounts_found': analysis['amounts'],
                    'keywords_found': analysis['keywords']
                }
            
            return None
        except Exception as e:
            print(f"Error analyzing email content: {e}")
            return None
    
    def _extract_financial_links(self, text):
        """Extract potential financial/receipt links from email text"""
        import re
        
        financial_patterns = [
            r'https?://[^\s<>"]*(?:receipt|invoice|bill|payment|transaction)[^\s<>"]*',
            r'https?://[^\s<>"]*(?:квитанц|счет|платеж|оплат)[^\s<>"]*',
            r'https?://[^\s<>"]*(?:facture|rechnung|paiement|zahlung)[^\s<>"]*',
        ]
        
        links = []
        for pattern in financial_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            links.extend(matches)
        
        return list(set(links))  # Remove duplicates
    
    def _extract_text(self, file_data, mime_type):
        """Extract text from different file types"""
        text = ""
        
        try:
            if mime_type == 'application/pdf':
                text = self._extract_from_pdf(file_data)
            elif mime_type.startswith('image/'):
                text = self._extract_from_image(file_data)
            elif mime_type.startswith('text/'):
                text = file_data.decode('utf-8', errors='ignore')
            
            return text.strip()
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""
    
    def _extract_from_pdf(self, file_data):
        """Extract text from PDF"""
        text = ""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_data))
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            print(f"PDF extraction error: {e}")
        
        return text
    
    def _extract_from_image(self, file_data):
        """Extract text from image using OCR"""
        try:
            image = Image.open(io.BytesIO(file_data))
            # Use multiple languages for OCR
            text = pytesseract.image_to_string(
                image, 
                lang='rus+eng+deu+fra',  # Russian, English, German, French
                config='--psm 6'
            )
            return text
        except Exception as e:
            print(f"OCR error: {e}")
            return ""
    
    def _analyze_financial_content(self, text):
        """Analyze text to determine if it contains financial information"""
        text_lower = text.lower()
        
        # Detect language
        try:
            language = detect(text)
            if language not in self.financial_keywords:
                language = 'en'  # Default to English
        except:
            language = 'en'
        
        # Count financial keywords
        keywords_found = []
        keyword_count = 0
        
        # Check keywords for detected language and English as fallback
        for lang in [language, 'en']:
            if lang in self.financial_keywords:
                for keyword in self.financial_keywords[lang]:
                    if keyword in text_lower:
                        keywords_found.append(keyword)
                        keyword_count += text_lower.count(keyword)
        
        # Find monetary amounts
        amounts_found = []
        for pattern in self.amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            amounts_found.extend(matches)
        
        # Calculate financial score
        score = 0
        score += min(keyword_count * 2, 20)  # Max 20 points for keywords
        score += min(len(amounts_found) * 5, 20)  # Max 20 points for amounts
        
        # Bonus for specific patterns
        if re.search(r'(invoice|счет|facture|rechnung)', text_lower):
            score += 10
        if re.search(r'(receipt|квитанция|reçu|quittung)', text_lower):
            score += 10
        
        is_financial = score >= 15 or len(amounts_found) > 0
        
        return {
            'is_financial': is_financial,
            'score': score,
            'language': language,
            'keywords': keywords_found[:5],  # Top 5 keywords
            'amounts': amounts_found[:3]     # Top 3 amounts
        }
import os
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64
import email
from datetime import datetime, timedelta

class GmailClient:
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self, credentials_file='../config/credentials.json'):
        self.credentials_file = credentials_file
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Gmail API"""
        creds = None
        
        # Check if token.pickle exists
        if os.path.exists('../config/token.pickle'):
            with open('../config/token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # If there are no valid credentials, request authorization
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open('../config/token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('gmail', 'v1', credentials=creds)
    
    def search_emails_with_attachments(self, days_back=30, query_extra=""):
        """Search for emails with attachments in the last N days"""
        # Calculate date
        date_from = datetime.now() - timedelta(days=days_back)
        date_str = date_from.strftime('%Y/%m/%d')
        
        # Gmail search query
        query = f'has:attachment after:{date_str} {query_extra}'
        
        try:
            result = self.service.users().messages().list(
                userId='me', q=query, maxResults=100
            ).execute()
            
            messages = result.get('messages', [])
            return messages
        except Exception as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_message_details(self, message_id):
        """Get detailed message information including attachments"""
        try:
            message = self.service.users().messages().get(
                userId='me', id=message_id, format='full'
            ).execute()
            
            return self._parse_message(message)
        except Exception as error:
            print(f'Error getting message {message_id}: {error}')
            return None
    
    def _parse_message(self, message):
        """Parse Gmail message to extract useful information"""
        payload = message['payload']
        headers = payload.get('headers', [])
        
        # Extract basic info
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        
        # Create reliable Gmail URL using search by subject
        import urllib.parse
        search_query = urllib.parse.quote(f'subject:"{subject[:50]}"')
        
        message_data = {
            'id': message['id'],
            'subject': subject,
            'sender': sender,
            'date': date,
            'attachments': [],
            'body_text': '',
            'gmail_url': f"https://mail.google.com/mail/#search/{search_query}"
        }
        
        # Extract email body text
        message_data['body_text'] = self._extract_body_text(payload)
        
        # Extract attachments
        if 'parts' in payload:
            self._extract_attachments(payload['parts'], message_data)
        elif payload.get('body', {}).get('attachmentId'):
            # Single attachment
            self._extract_single_attachment(payload, message_data)
        
        return message_data
    
    def _extract_attachments(self, parts, message_data):
        """Extract attachments from message parts"""
        for part in parts:
            if part.get('filename'):
                attachment_info = {
                    'filename': part['filename'],
                    'mime_type': part['mimeType'],
                    'attachment_id': part['body'].get('attachmentId'),
                    'size': part['body'].get('size', 0)
                }
                message_data['attachments'].append(attachment_info)
            
            # Check nested parts
            if 'parts' in part:
                self._extract_attachments(part['parts'], message_data)
    
    def _extract_single_attachment(self, payload, message_data):
        """Extract single attachment"""
        attachment_info = {
            'filename': payload.get('filename', 'attachment'),
            'mime_type': payload['mimeType'],
            'attachment_id': payload['body'].get('attachmentId'),
            'size': payload['body'].get('size', 0)
        }
        message_data['attachments'].append(attachment_info)
    
    def download_attachment(self, message_id, attachment_id):
        """Download attachment content"""
        try:
            attachment = self.service.users().messages().attachments().get(
                userId='me', messageId=message_id, id=attachment_id
            ).execute()
            
            data = attachment['data']
            return base64.urlsafe_b64decode(data)
        except Exception as error:
            print(f'Error downloading attachment: {error}')
            return None
    
    def _extract_body_text(self, payload):
        """Extract body text from email payload"""
        body_text = ""
        
        def decode_body_data(data):
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                except:
                    return ""
            return ""
        
        # Check if payload has body data directly
        if payload.get('body', {}).get('data'):
            body_text = decode_body_data(payload['body']['data'])
        
        # Check parts for text content
        elif 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                
                if mime_type == 'text/plain' or mime_type == 'text/html':
                    if part.get('body', {}).get('data'):
                        body_text += decode_body_data(part['body']['data']) + "\n"
                
                # Check nested parts
                elif 'parts' in part:
                    for nested_part in part['parts']:
                        nested_mime = nested_part.get('mimeType', '')
                        if nested_mime == 'text/plain' or nested_mime == 'text/html':
                            if nested_part.get('body', {}).get('data'):
                                body_text += decode_body_data(nested_part['body']['data']) + "\n"
        
        return body_text.strip()
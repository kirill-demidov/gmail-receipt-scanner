import sqlite3
from datetime import datetime
import json
import os

class DocumentDatabase:
    def __init__(self, db_path='../data/documents.db'):
        # Ensure the directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS financial_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    filename TEXT,
                    sender TEXT,
                    subject TEXT,
                    email_date TEXT,
                    mime_type TEXT,
                    language TEXT,
                    financial_score INTEGER,
                    text_content TEXT,
                    amounts_found TEXT,
                    keywords_found TEXT,
                    gmail_url TEXT,
                    email_body TEXT,
                    document_type TEXT DEFAULT 'attachment',
                    processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(message_id, filename)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    emails_scanned INTEGER,
                    documents_found INTEGER,
                    status TEXT
                )
            ''')
    
    def save_document(self, message_data, doc_analysis, document_type='attachment'):
        """Save financial document to database"""
        try:
            filename = doc_analysis.get('filename', 'email_content')
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO financial_documents 
                    (message_id, filename, sender, subject, email_date, mime_type, 
                     language, financial_score, text_content, amounts_found, keywords_found,
                     gmail_url, email_body, document_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    message_data['id'],
                    filename,
                    message_data['sender'],
                    message_data['subject'],
                    message_data['date'],
                    doc_analysis.get('mime_type', 'text/plain'),
                    doc_analysis['language'],
                    doc_analysis['financial_score'],
                    doc_analysis.get('text', ''),
                    json.dumps(doc_analysis['amounts_found']),
                    json.dumps(doc_analysis['keywords_found']),
                    message_data.get('gmail_url', ''),
                    message_data.get('body_text', ''),
                    document_type
                ))
                return True
        except Exception as e:
            print(f"Database error: {e}")
            return False
    
    def save_scan_history(self, emails_scanned, documents_found, status="completed"):
        """Save scan session history"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO scan_history (emails_scanned, documents_found, status)
                VALUES (?, ?, ?)
            ''', (emails_scanned, documents_found, status))
    
    def get_all_documents(self, limit=100):
        """Get all financial documents"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM financial_documents 
                ORDER BY processed_date DESC 
                LIMIT ?
            ''', (limit,))
            
            documents = []
            for row in cursor:
                doc = dict(row)
                doc['amounts_found'] = json.loads(doc['amounts_found'] or '[]')
                doc['keywords_found'] = json.loads(doc['keywords_found'] or '[]')
                documents.append(doc)
            
            return documents
    
    def search_documents(self, query, limit=50):
        """Search documents by text content, sender, or subject"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            search_term = f"%{query}%"
            
            cursor = conn.execute('''
                SELECT * FROM financial_documents 
                WHERE text_content LIKE ? OR sender LIKE ? OR subject LIKE ?
                ORDER BY financial_score DESC, processed_date DESC
                LIMIT ?
            ''', (search_term, search_term, search_term, limit))
            
            documents = []
            for row in cursor:
                doc = dict(row)
                doc['amounts_found'] = json.loads(doc['amounts_found'] or '[]')
                doc['keywords_found'] = json.loads(doc['keywords_found'] or '[]')
                documents.append(doc)
            
            return documents
    
    def get_scan_history(self, limit=10):
        """Get recent scan history"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM scan_history 
                ORDER BY scan_date DESC 
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor]
    
    def get_statistics(self):
        """Get database statistics"""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            
            # Total documents
            cursor = conn.execute('SELECT COUNT(*) as count FROM financial_documents')
            stats['total_documents'] = cursor.fetchone()[0]
            
            # Documents by language
            cursor = conn.execute('''
                SELECT language, COUNT(*) as count 
                FROM financial_documents 
                GROUP BY language
            ''')
            stats['by_language'] = {row[0]: row[1] for row in cursor}
            
            # Recent scans
            cursor = conn.execute('''
                SELECT COUNT(*) as count 
                FROM scan_history 
                WHERE scan_date > datetime('now', '-7 days')
            ''')
            stats['recent_scans'] = cursor.fetchone()[0]
            
            return stats
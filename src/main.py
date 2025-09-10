#!/usr/bin/env python3
"""
Receipt Scanner - Gmail финансовых документов
Сканирует Gmail на предмет квитанций, чеков, счетов и других финансовых документов
"""

import os
import sys
from gmail_client import GmailClient
from document_processor import DocumentProcessor
from database import DocumentDatabase

class ReceiptScanner:
    def __init__(self):
        self.gmail_client = None
        self.doc_processor = DocumentProcessor()
        self.db = DocumentDatabase()
    
    def initialize(self):
        """Initialize Gmail client"""
        try:
            self.gmail_client = GmailClient()
            print("✓ Gmail API подключен")
            return True
        except FileNotFoundError:
            print("❌ Файл credentials.json не найден в папке config/")
            print("Инструкция по настройке:")
            print("1. Перейти в Google Cloud Console")
            print("2. Создать проект и включить Gmail API")
            print("3. Создать OAuth 2.0 credentials")
            print("4. Скачать JSON файл как config/credentials.json")
            return False
        except Exception as e:
            print(f"❌ Ошибка инициализации: {e}")
            return False
    
    def scan_gmail(self, days_back=30):
        """Сканировать Gmail за последние N дней"""
        if not self.gmail_client:
            print("❌ Gmail client не инициализирован")
            return
        
        print(f"🔍 Поиск писем с вложениями за последние {days_back} дней...")
        
        # Поиск писем с вложениями
        messages = self.gmail_client.search_emails_with_attachments(days_back)
        
        print(f"📧 Найдено {len(messages)} писем с вложениями")
        
        documents_found = 0
        processed_messages = 0
        
        for message in messages:
            try:
                # Получить детали сообщения
                message_data = self.gmail_client.get_message_details(message['id'])
                if not message_data:
                    continue
                
                processed_messages += 1
                print(f"📧 Обрабатывается: {message_data['subject'][:50]}...")
                
                # Обработать вложения
                for attachment in message_data['attachments']:
                    if self._should_process_attachment(attachment):
                        doc_analysis = self._process_attachment(
                            message_data, attachment
                        )
                        
                        if doc_analysis:
                            self.db.save_document(message_data, doc_analysis, 'attachment')
                            documents_found += 1
                            print(f"  ✓ Найден финансовый документ: {attachment['filename']}")
                
                # Также проверить содержимое самого письма
                if message_data.get('body_text'):
                    email_analysis = self.doc_processor.analyze_email_content(
                        message_data['body_text'], 
                        message_data['subject']
                    )
                    
                    if email_analysis:
                        # Только сохраняем если нет вложений или финансовая оценка высокая
                        if not message_data['attachments'] or email_analysis['financial_score'] > 25:
                            self.db.save_document(message_data, email_analysis, 'email_content')
                            documents_found += 1
                            print(f"  ✓ Найден финансовый контент в письме: {message_data['subject'][:50]}...")
                
            except Exception as e:
                print(f"❌ Ошибка обработки сообщения: {e}")
                continue
        
        # Сохранить историю сканирования
        self.db.save_scan_history(processed_messages, documents_found)
        
        print(f"\n📊 Результаты сканирования:")
        print(f"📧 Писем обработано: {processed_messages}")
        print(f"📄 Финансовых документов найдено: {documents_found}")
        
        return documents_found
    
    def _should_process_attachment(self, attachment):
        """Проверить, стоит ли обрабатывать вложение"""
        filename = attachment['filename'].lower()
        mime_type = attachment['mime_type']
        
        # Поддерживаемые типы файлов
        supported_types = [
            'application/pdf',
            'image/jpeg', 'image/jpg', 'image/png', 'image/tiff',
            'text/plain'
        ]
        
        # Исключить слишком большие файлы (>10MB)
        if attachment.get('size', 0) > 10 * 1024 * 1024:
            return False
        
        # Проверить расширение файла
        financial_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.txt']
        if not any(filename.endswith(ext) for ext in financial_extensions):
            return False
        
        return mime_type in supported_types
    
    def _process_attachment(self, message_data, attachment):
        """Обработать вложение"""
        try:
            # Скачать вложение
            file_data = self.gmail_client.download_attachment(
                message_data['id'], 
                attachment['attachment_id']
            )
            
            if not file_data:
                return None
            
            # Обработать документ
            return self.doc_processor.process_attachment(
                file_data,
                attachment['filename'],
                attachment['mime_type']
            )
            
        except Exception as e:
            print(f"Ошибка обработки вложения {attachment['filename']}: {e}")
            return None
    
    def show_results(self, limit=20):
        """Показать найденные документы"""
        documents = self.db.get_all_documents(limit)
        
        if not documents:
            print("📄 Финансовые документы не найдены")
            return
        
        print(f"\n📄 Найдено {len(documents)} финансовых документов:\n")
        
        for doc in documents:
            print(f"📁 {doc['filename']}")
            print(f"   📧 От: {doc['sender']}")
            print(f"   📅 Дата: {doc['email_date']}")
            print(f"   🏷️  Тема: {doc['subject'][:60]}...")
            print(f"   🔢 Оценка: {doc['financial_score']}")
            print(f"   💰 Суммы: {', '.join(doc['amounts_found'])}")
            print(f"   🔤 Ключевые слова: {', '.join(doc['keywords_found'])}")
            print("-" * 60)
    
    def search_documents(self, query):
        """Поиск по документам"""
        documents = self.db.search_documents(query)
        
        if not documents:
            print(f"📄 Документы по запросу '{query}' не найдены")
            return
        
        print(f"\n🔍 Найдено {len(documents)} документов по запросу '{query}':\n")
        
        for doc in documents:
            print(f"📁 {doc['filename']} (оценка: {doc['financial_score']})")
            print(f"   📧 От: {doc['sender']}")
            print(f"   💰 Суммы: {', '.join(doc['amounts_found'])}")
            print("-" * 40)

def main():
    scanner = ReceiptScanner()
    
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python main.py init     - Настройка Gmail API")
        print("  python main.py scan     - Сканировать Gmail")
        print("  python main.py scan 7   - Сканировать за 7 дней")
        print("  python main.py show     - Показать найденные документы")
        print("  python main.py search 'банк'  - Поиск по документам")
        return
    
    command = sys.argv[1]
    
    if command == "init":
        if scanner.initialize():
            print("✓ Система готова к использованию")
        else:
            print("❌ Ошибка инициализации")
    
    elif command == "scan":
        if not scanner.initialize():
            return
        
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        scanner.scan_gmail(days)
    
    elif command == "show":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        scanner.show_results(limit)
    
    elif command == "search":
        if len(sys.argv) < 3:
            print("❌ Укажите поисковый запрос")
            return
        
        query = sys.argv[2]
        scanner.search_documents(query)
    
    else:
        print(f"❌ Неизвестная команда: {command}")

if __name__ == "__main__":
    main()
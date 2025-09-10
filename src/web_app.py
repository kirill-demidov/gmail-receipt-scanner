from flask import Flask, render_template, request, jsonify, redirect, url_for
from database import DocumentDatabase
from main import ReceiptScanner
import os
import threading

app = Flask(__name__, template_folder='../templates')
db = DocumentDatabase()
scanner = ReceiptScanner()

# Global variable to track scanning status
scanning_status = {
    'is_scanning': False,
    'progress': '',
    'emails_processed': 0,
    'documents_found': 0
}

@app.route('/')
def index():
    """Главная страница"""
    stats = db.get_statistics()
    recent_docs = db.get_all_documents(10)
    return render_template('index.html', stats=stats, documents=recent_docs)

@app.route('/documents')
def documents():
    """Страница со всеми документами"""
    limit = request.args.get('limit', 50, type=int)
    docs = db.get_all_documents(limit)
    return render_template('documents.html', documents=docs)

@app.route('/search')
def search():
    """Поиск документов"""
    query = request.args.get('q', '')
    if query:
        docs = db.search_documents(query)
        return render_template('search_results.html', documents=docs, query=query)
    return render_template('search.html')

@app.route('/api/documents')
def api_documents():
    """API для получения документов"""
    limit = request.args.get('limit', 50, type=int)
    docs = db.get_all_documents(limit)
    return jsonify(docs)

@app.route('/api/search')
def api_search():
    """API для поиска документов"""
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    docs = db.search_documents(query)
    return jsonify(docs)

@app.route('/api/stats')
def api_stats():
    """API для получения статистики"""
    return jsonify(db.get_statistics())

@app.route('/scan')
def scan_page():
    """Страница запуска сканирования"""
    return render_template('scan.html', status=scanning_status)

@app.route('/start_scan', methods=['POST'])
def start_scan():
    """Запуск сканирования"""
    if scanning_status['is_scanning']:
        return jsonify({'error': 'Сканирование уже выполняется'}), 400
    
    days = int(request.form.get('days', 30))
    
    # Запуск сканирования в отдельном потоке
    thread = threading.Thread(target=run_scan, args=(days,))
    thread.daemon = True
    thread.start()
    
    return redirect(url_for('scan_page'))

@app.route('/api/scan_status')
def scan_status():
    """API для получения статуса сканирования"""
    return jsonify(scanning_status)

def run_scan(days):
    """Функция для выполнения сканирования в фоне"""
    global scanning_status
    
    scanning_status['is_scanning'] = True
    scanning_status['progress'] = 'Инициализация...'
    scanning_status['emails_processed'] = 0
    scanning_status['documents_found'] = 0
    
    try:
        # Инициализация
        if not scanner.initialize():
            scanning_status['progress'] = 'Ошибка инициализации Gmail API'
            scanning_status['is_scanning'] = False
            return
        
        scanning_status['progress'] = f'Поиск писем за последние {days} дней...'
        
        # Запуск сканирования
        documents_found = scanner.scan_gmail(days)
        
        scanning_status['documents_found'] = documents_found
        scanning_status['progress'] = f'Сканирование завершено! Найдено {documents_found} документов.'
        
    except Exception as e:
        scanning_status['progress'] = f'Ошибка: {str(e)}'
    
    finally:
        scanning_status['is_scanning'] = False

if __name__ == '__main__':
    app.run(debug=True, port=5000)
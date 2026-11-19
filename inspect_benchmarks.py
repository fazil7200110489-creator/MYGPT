import sys
sys.path.insert(0, 'backend')
from app.services.document_manager import DocumentManager

dm = DocumentManager()
doc = dm.get_document("9b2e10a5-1a90-405d-adda-4460ead30bc2")
p22 = [p for p in doc['pages'] if p['page_number'] == 22][0]
print("=== Page 22 text ===")
print(p22['text'][:1500])

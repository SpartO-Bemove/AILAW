@@ .. @@
 import logging
 import time
 import threading
 from typing import List, Optional
 from langchain.schema import Document
 from langchain_community.vectorstores import Chroma
-from .neuralex_main import neuralex
-from .document_loader import DocumentLoader
+from neuralex_main import neuralex
+from document_loader import DocumentLoader
 
 logger = logging.getLogger(__name__)
 
 class EnhancedNeuralex(neuralex):
     """Расширенная версия neuralex с поддержкой дополнительных документов"""
     
     def __init__(self, llm, embeddings, vector_store, redis_url=None, documents_path="documents"):
         super().__init__(llm, embeddings, vector_store, redis_url)
         
         self.document_loader = DocumentLoader(documents_path)
         self.additional_documents_loaded = False
         self.documents_stats = {}
         
         # Загружаем дополнительные документы при инициализации
         self._load_additional_documents()
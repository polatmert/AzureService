import os
import logging
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from typing import Dict, Any, List
import json
from .docx_converter import DocxConverter

logger = logging.getLogger(__name__)

class DocumentIntelligenceService:
    def __init__(self):
        # Azure Document Intelligence yapılandırması
        self.endpoint = os.getenv("AZURE_DOCUMENT_ENDPOINT", "https://seraph-document.cognitiveservices.azure.com/")
        self.key = os.getenv("AZURE_DOCUMENT_KEY", "7rDfrNqhvRl0bmMXVQw1rvcOXoN1FBcghe3KunshjFYlktTZGw9oJQQJ99BGACfhMk5XJ3w3AAALACOGaGf9")
        
        # Client oluştur
        self.client = DocumentIntelligenceClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.key)
        )
        
        logger.info("Azure Document Intelligence service initialized")
    
    async def analyze_document(self, document_bytes: bytes, content_type: str = "application/pdf") -> Dict[str, Any]:
        """
        Belgeyi Azure Document Intelligence ile analiz eder
        
        Args:
            document_bytes: Belge dosyası bytes formatında
            content_type: Dosya MIME tipi
            
        Returns:
            Analiz sonuçlarını içeren dictionary
        """
        try:
            logger.info(f"Döküman analizi başlatılıyor, content_type: {content_type}")
            logger.info(f"Dosya boyutu: {len(document_bytes)} bytes")
            
            # DOCX dosyaları için özel validasyon
            if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                logger.info("DOCX dosyası tespit edildi, validasyon yapılıyor...")
                
                # DOCX dosyasının geçerli olup olmadığını kontrol et
                if not DocxConverter.validate_docx(document_bytes):
                    raise Exception("DOCX dosyası bozuk veya geçersiz format")
                
                logger.info("DOCX validasyonu başarılı")
                
                # Analyze request oluştur
                analyze_request = AnalyzeDocumentRequest(
                    bytes_source=document_bytes
                )
            else:
                # Analyze request oluştur
                analyze_request = AnalyzeDocumentRequest(
                    bytes_source=document_bytes
                )
            
            logger.info("Azure Document Intelligence API'sine istek gönderiliyor...")
            
            # DOCX dosyaları için prebuilt-read modeli kullan
            if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                model_id = "prebuilt-read"
                logger.info("DOCX için prebuilt-read modeli kullanılıyor")
            else:
                model_id = "prebuilt-document"
            
            # Belge analizi başlat
            poller = self.client.begin_analyze_document(
                model_id=model_id,
                body=analyze_request
            )
            
            result = poller.result()
            
            # Sonuçları işle
            analysis_result = self._process_analysis_result(result)
            
            logger.info("Döküman analizi başarıyla tamamlandı")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Döküman analizi sırasında hata: {str(e)}")
            raise Exception(f"Döküman analizi başarısız: {str(e)}")
    
    async def analyze_layout(self, document_bytes: bytes, content_type: str = "application/pdf") -> Dict[str, Any]:
        """
        Belgenin layout'unu analiz eder
        
        Args:
            document_bytes: Belge dosyası bytes formatında
            content_type: Dosya MIME tipi
            
        Returns:
            Layout analiz sonuçlarını içeren dictionary
        """
        try:
            logger.info(f"Layout analizi başlatılıyor, content_type: {content_type}")
            
            # Analyze request oluştur
            analyze_request = AnalyzeDocumentRequest(
                bytes_source=document_bytes
            )
            
            # Layout analizi
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=analyze_request
            )
            
            result = poller.result()
            
            # Layout sonuçlarını işle
            layout_result = self._process_layout_result(result)
            
            logger.info("Layout analizi başarıyla tamamlandı")
            return layout_result
            
        except Exception as e:
            logger.error(f"Layout analizi sırasında hata: {str(e)}")
            raise Exception(f"Layout analizi başarısız: {str(e)}")
    
    async def extract_tables(self, document_bytes: bytes, content_type: str = "application/pdf") -> List[Dict]:
        """
        Belgeden tabloları çıkarır
        
        Args:
            document_bytes: Belge dosyası bytes formatında
            content_type: Dosya MIME tipi
            
        Returns:
            Tabloları içeren list
        """
        try:
            logger.info(f"Tablo çıkarma işlemi başlatılıyor, content_type: {content_type}")
            
            # Analyze request oluştur
            analyze_request = AnalyzeDocumentRequest(
                bytes_source=document_bytes
            )
            
            # Belgeyi analiz et
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=analyze_request
            )
            
            result = poller.result()
            
            # Tabloları çıkar
            tables = self._extract_tables_from_result(result)
            
            logger.info(f"{len(tables)} tablo çıkarıldı")
            return tables
            
        except Exception as e:
            logger.error(f"Tablo çıkarma sırasında hata: {str(e)}")
            raise Exception(f"Tablo çıkarma başarısız: {str(e)}")
    
    def _process_analysis_result(self, result) -> Dict[str, Any]:
        """
        Analiz sonuçlarını işler ve düzenler
        """
        processed_result = {
            "content": "",
            "pages": [],
            "paragraphs": [],
            "key_value_pairs": [],
            "entities": []
        }
        
        # İçeriği al
        if result.content:
            processed_result["content"] = result.content
        
        # Sayfaları işle
        if result.pages:
            for page in result.pages:
                page_info = {
                    "page_number": page.page_number,
                    "width": page.width,
                    "height": page.height,
                    "unit": page.unit,
                    "lines": []
                }
                
                if page.lines:
                    for line in page.lines:
                        page_info["lines"].append({
                            "content": line.content,
                            "spans": [{"offset": span.offset, "length": span.length} for span in line.spans] if line.spans else []
                        })
                
                processed_result["pages"].append(page_info)
        
        # Paragrafları işle
        if result.paragraphs:
            for paragraph in result.paragraphs:
                processed_result["paragraphs"].append({
                    "content": paragraph.content,
                    "role": paragraph.role if hasattr(paragraph, 'role') else None,
                    "spans": [{"offset": span.offset, "length": span.length} for span in paragraph.spans] if paragraph.spans else []
                })
        
        # Anahtar-değer çiftlerini işle
        if result.key_value_pairs:
            for kv_pair in result.key_value_pairs:
                kv_info = {
                    "key": kv_pair.key.content if kv_pair.key else None,
                    "value": kv_pair.value.content if kv_pair.value else None,
                    "confidence": kv_pair.confidence if hasattr(kv_pair, 'confidence') else None
                }
                processed_result["key_value_pairs"].append(kv_info)
        
        return processed_result
    
    def _process_layout_result(self, result) -> Dict[str, Any]:
        """
        Layout analiz sonuçlarını işler
        """
        layout_result = {
            "content": "",
            "pages": [],
            "tables": [],
            "paragraphs": []
        }
        
        # İçeriği al
        if result.content:
            layout_result["content"] = result.content
        
        # Sayfaları işle (detaylı layout bilgisiyle)
        if result.pages:
            for page in result.pages:
                page_info = {
                    "page_number": page.page_number,
                    "width": page.width,
                    "height": page.height,
                    "unit": page.unit,
                    "lines": [],
                    "words": []
                }
                
                if page.lines:
                    for line in page.lines:
                        page_info["lines"].append({
                            "content": line.content,
                            "spans": [{"offset": span.offset, "length": span.length} for span in line.spans] if line.spans else []
                        })
                
                if page.words:
                    for word in page.words:
                        page_info["words"].append({
                            "content": word.content,
                            "confidence": word.confidence if hasattr(word, 'confidence') else None,
                            "spans": [{"offset": span.offset, "length": span.length} for span in word.spans] if word.spans else []
                        })
                
                layout_result["pages"].append(page_info)
        
        # Tabloları işle
        if result.tables:
            layout_result["tables"] = self._extract_tables_from_result(result)
        
        # Paragrafları işle
        if result.paragraphs:
            for paragraph in result.paragraphs:
                layout_result["paragraphs"].append({
                    "content": paragraph.content,
                    "role": paragraph.role if hasattr(paragraph, 'role') else None,
                    "spans": [{"offset": span.offset, "length": span.length} for span in paragraph.spans] if paragraph.spans else []
                })
        
        return layout_result
    
    def _extract_tables_from_result(self, result) -> List[Dict]:
        """
        Sonuçlardan tabloları çıkarır
        """
        tables = []
        
        if result.tables:
            for table in result.tables:
                table_data = {
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "cells": []
                }
                
                if table.cells:
                    for cell in table.cells:
                        cell_data = {
                            "content": cell.content,
                            "row_index": cell.row_index,
                            "column_index": cell.column_index,
                            "row_span": cell.row_span if hasattr(cell, 'row_span') else 1,
                            "column_span": cell.column_span if hasattr(cell, 'column_span') else 1,
                            "kind": cell.kind if hasattr(cell, 'kind') else None
                        }
                        table_data["cells"].append(cell_data)
                
                tables.append(table_data)
        
        return tables

# Global service instance
document_intelligence_service = DocumentIntelligenceService()

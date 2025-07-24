import os
import logging
from typing import Dict, Any, Optional
import json
import time
from .openai_service import OpenAIService

logger = logging.getLogger(__name__)

class OpenAIAssistantService:
    def __init__(self):
        # Mevcut OpenAI service'ini kullan
        self.openai_service = OpenAIService()
        
        # Assistant ID
        self.assistant_id = "asst_MhSwILOybr3VZMDpBy6vJp36"
        
        logger.info(f"OpenAI Assistant Service başlatıldı, Assistant ID: {self.assistant_id}")
    
    async def score_document(self, document_analysis: Dict[str, Any], scoring_criteria: Optional[str] = None) -> Dict[str, Any]:
        """
        Analiz edilmiş belgeyi Assistant'a gönderip skorlama yapar
        
        Args:
            document_analysis: Azure Document Intelligence'dan gelen analiz sonucu
            scoring_criteria: Özel skorlama kriterleri (opsiyonel)
            
        Returns:
            Dict: Skorlama sonuçları
        """
        try:
            logger.info("Belge skorlama işlemi başlatılıyor...")
            
            # Belge içeriğini hazırla
            document_content = self._prepare_document_content(document_analysis)
            
            # Skorlama prompt'unu oluştur
            scoring_prompt = self._create_scoring_prompt(document_content, scoring_criteria)
            
            logger.info(f"Assistant {self.assistant_id} ile skorlama yapılıyor...")
            
            # Mevcut OpenAI service'ini kullan
            assistant_response = await self.openai_service.use_assistant(
                prompt=scoring_prompt,
                assistant_id=self.assistant_id
            )
            
            # Skorlama sonuçlarını işle
            scoring_result = self._process_scoring_result(assistant_response, document_analysis)
            
            logger.info("Belge skorlama işlemi başarıyla tamamlandı")
            return scoring_result
            
        except Exception as e:
            logger.error(f"Belge skorlama sırasında hata: {str(e)}")
            raise Exception(f"Skorlama işlemi başarısız: {str(e)}")
    
    def _prepare_document_content(self, document_analysis: Dict[str, Any]) -> str:
        """Belge analizini skorlama için uygun formata dönüştürür"""
        try:
            content_parts = []
            
            # Dosya bilgileri
            if "file_info" in document_analysis:
                file_info = document_analysis["file_info"]
                content_parts.append(f"Dosya Adı: {file_info.get('filename', 'Bilinmiyor')}")
                content_parts.append(f"Dosya Boyutu: {file_info.get('size', 0)} bytes")
                content_parts.append(f"Dosya Tipi: {file_info.get('content_type', 'Bilinmiyor')}")
                content_parts.append("---")
            
            # Ana içerik
            if "content" in document_analysis:
                content_parts.append("BELGE İÇERİĞİ:")
                content_parts.append(document_analysis["content"])
                content_parts.append("---")
            
            # Paragraflar
            if "paragraphs" in document_analysis and document_analysis["paragraphs"]:
                content_parts.append("PARAGRAFLAR:")
                for i, para in enumerate(document_analysis["paragraphs"], 1):
                    content_parts.append(f"{i}. {para}")
                content_parts.append("---")
            
            # Anahtar-değer çiftleri
            if "key_value_pairs" in document_analysis and document_analysis["key_value_pairs"]:
                content_parts.append("ANAHTAR-DEĞER ÇİFTLERİ:")
                for kv in document_analysis["key_value_pairs"]:
                    content_parts.append(f"• {kv}")
                content_parts.append("---")
            
            # Tablolar
            if "tables" in document_analysis and document_analysis["tables"]:
                content_parts.append("TABLOLAR:")
                for i, table in enumerate(document_analysis["tables"], 1):
                    content_parts.append(f"Tablo {i}: {table}")
                content_parts.append("---")
            
            return "\n".join(content_parts)
            
        except Exception as e:
            logger.error(f"Belge içeriği hazırlama sırasında hata: {str(e)}")
            return str(document_analysis)
    
    def _create_scoring_prompt(self, document_content: str, scoring_criteria: Optional[str] = None) -> str:
        """Skorlama için prompt oluşturur"""
        
        base_prompt = f"""
Lütfen aşağıdaki belgeyi analiz edip skorlayın:

{document_content}

SKORLAMA KRİTERLERİ:
"""
        
        if scoring_criteria:
            base_prompt += f"\n{scoring_criteria}\n"
        else:
            base_prompt += """
1. İçerik Kalitesi (0-100): Belgenin içeriğinin netliği, tutarlılığı ve kapsamlılığı
2. Yapısal Düzen (0-100): Belgenin formatı, düzeni ve okunabilirliği  
3. Teknik Doğruluk (0-100): Teknik bilgilerin doğruluğu ve güncelliği
4. Completeness (0-100): Belgenin eksiksizlik durumu
5. Professional Quality (0-100): Profesyonel standartlara uygunluk

LÜTFEN SONUCU ŞU FORMATTA VERİN:
{
    "overall_score": toplam_skor,
    "content_quality": skor,
    "structural_layout": skor, 
    "technical_accuracy": skor,
    "completeness": skor,
    "professional_quality": skor,
    "detailed_feedback": "detaylı_geri_bildirim",
    "strengths": ["güçlü_yön_1", "güçlü_yön_2"],
    "improvements": ["iyileştirme_önerisi_1", "iyileştirme_önerisi_2"]
}
"""
        
        return base_prompt
    
    def _process_scoring_result(self, assistant_response: Dict[str, Any], original_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Assistant'ın skorlama sonucunu işler"""
        try:
            # OpenAI service'den gelen response'u işle
            response_content = assistant_response.get("response", "")
            
            # JSON formatını bulmaya çalış
            import re
            json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group()
                scoring_data = json.loads(json_str)
            else:
                # JSON bulunamazsa basit parsing yap
                scoring_data = {
                    "overall_score": 0,
                    "detailed_feedback": response_content,
                    "error": "JSON format bulunamadı"
                }
            
            # Sonucu zenginleştir
            result = {
                "success": True,
                "scoring_timestamp": time.time(),
                "assistant_id": self.assistant_id,
                "document_info": original_analysis.get("file_info", {}),
                "scoring_results": scoring_data,
                "raw_response": response_content,
                "assistant_metadata": assistant_response.get("metadata", {})
            }
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing hatası: {str(e)}")
            return {
                "success": False,
                "error": f"JSON parsing hatası: {str(e)}",
                "raw_response": assistant_response.get("response", "")
            }
        except Exception as e:
            logger.error(f"Skorlama sonucu işleme hatası: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "raw_response": str(assistant_response)
            }

# Singleton instance
openai_assistant_service = OpenAIAssistantService()

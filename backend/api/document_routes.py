from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse, Response
import logging
from typing import List, Dict, Any, Optional
import io
import tempfile
import os
from datetime import datetime
import re

import json
from ..services.document_intelligence_service import document_intelligence_service
from ..services.openai_assistant_service import openai_assistant_service, OpenAIService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/document", tags=["document"])

@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_document(
    file: UploadFile = File(..., description="Analiz edilecek belge dosyası")
):
    """
    Yüklenen belgeyi Azure Document Intelligence ile analiz eder
    
    - **file**: PDF, DOCX, TXT, JPG, PNG formatında belge
    
    Returns:
        - Belge içeriği
        - Sayfa bilgileri  
        - Paragraflar
        - Anahtar-değer çiftleri
        - Varlıklar
    """
    try:
        logger.info(f"Döküman analizi isteği alındı: {file.filename}")
        
        # Dosya tipini kontrol et
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "image/jpeg",
            "image/jpg", 
            "image/png",
            "image/tiff",
            "application/msword"  # .doc dosyaları için
        ]
        
        # Dosya uzantısını da kontrol et
        allowed_extensions = [".pdf", ".docx", ".doc", ".txt", ".jpg", ".jpeg", ".png", ".tiff", ".tif"]
        
        file_extension = None
        if file.filename:
            file_extension = "." + file.filename.split(".")[-1].lower() if "." in file.filename else None
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Desteklenmeyen dosya tipi: {file.content_type}. Desteklenen tipler: {', '.join(allowed_types)}"
            )
            
        if file_extension and file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Desteklenmeyen dosya uzantısı: {file_extension}. Desteklenen uzantılar: {', '.join(allowed_extensions)}"
            )
        
        # Dosyayı oku
        file_content = await file.read()
        
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Boş dosya yüklenemez")
            
        # Dosya boyutunu kontrol et (50MB limit)
        max_file_size = 50 * 1024 * 1024  # 50MB
        if len(file_content) > max_file_size:
            raise HTTPException(
                status_code=400, 
                detail=f"Dosya çok büyük. Maksimum boyut: 50MB, Yüklenen dosya: {len(file_content) / 1024 / 1024:.2f}MB"
            )
            
        logger.info(f"Dosya validasyonu başarılı: {file.filename}, boyut: {len(file_content)} bytes, tip: {file.content_type}")
        
        # Document Intelligence ile analiz et
        analysis_result = await document_intelligence_service.analyze_document(
            document_bytes=file_content,
            content_type=file.content_type
        )
        
        # Dosya bilgilerini ekle
        analysis_result["file_info"] = {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(file_content)
        }
        
        logger.info(f"Döküman analizi başarıyla tamamlandı: {file.filename}")
        
        return {
            "success": True,
            "message": "Döküman başarıyla analiz edildi",
            "data": analysis_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Döküman analizi sırasında hata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Döküman analizi başarısız: {str(e)}")

@router.post("/analyze-and-score", response_model=Dict[str, Any])
async def analyze_and_score_document(
    files: List[UploadFile] = File(..., description="Analiz ve skorlama yapılacak belge dosyaları"),
    scoring_criteria: Optional[str] = None
):
    """
    Yüklenen belgeleri Azure Document Intelligence ile analiz eder ve OpenAI Assistant ile skorlar
    
    - **files**: PDF, DOCX, TXT, JPG, PNG formatında belge dosyaları (birden fazla desteklenir)
    - **scoring_criteria**: Özel skorlama kriterleri (opsiyonel)
    
    Returns:
        - Her belge için doküman adı ve skoru
        - Batch işlem özeti
    """
    try:
        logger.info(f"Toplu döküman analizi ve skorlama isteği alındı: {len(files)} dosya")
        
        if not files:
            raise HTTPException(status_code=400, detail="En az bir dosya yüklenmelidir")
        
        # Dosya validasyonu
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "image/jpeg",
            "image/jpg", 
            "image/png",
            "image/tiff",
            "application/msword"
        ]
        
        allowed_extensions = [".pdf", ".docx", ".doc", ".txt", ".jpg", ".jpeg", ".png", ".tiff", ".tif"]
        max_file_size = 50 * 1024 * 1024  # 50MB
        
        # Tüm dosyaları önce validate et
        validated_files = []
        for file in files:
            # Dosya tipi kontrolü
            if file.content_type not in allowed_types:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Desteklenmeyen dosya tipi: {file.content_type} (dosya: {file.filename})"
                )
            
            # Dosya uzantısı kontrolü
            file_extension = None
            if file.filename:
                file_extension = "." + file.filename.split(".")[-1].lower() if "." in file.filename else None
            
            if file_extension and file_extension not in allowed_extensions:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Desteklenmeyen dosya uzantısı: {file_extension} (dosya: {file.filename})"
                )
            
            # Dosyayı oku
            file_content = await file.read()
            
            if len(file_content) == 0:
                raise HTTPException(status_code=400, detail=f"Boş dosya: {file.filename}")
                
            # Dosya boyutu kontrolü
            if len(file_content) > max_file_size:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Dosya çok büyük: {file.filename} ({len(file_content) / 1024 / 1024:.2f}MB > 50MB)"
                )
            
            validated_files.append({
                "filename": file.filename,
                "content": file_content,
                "content_type": file.content_type
            })
        
        logger.info(f"Tüm dosyalar validate edildi: {len(validated_files)} dosya")
        
        # Async olarak tüm dosyaları işle
        import asyncio
        
        async def process_single_document(file_data):
            """Tek bir dokümanı analiz ve skorla"""
            try:
                filename = file_data["filename"]
                content = file_data["content"]
                content_type = file_data["content_type"]
                
                logger.info(f"İşleniyor: {filename}")
                
                # 1. ADIM: Document Intelligence ile analiz et
                analysis_result = await document_intelligence_service.analyze_document(
                    document_bytes=content,
                    content_type=content_type
                )
                
                # Dosya bilgilerini ekle
                analysis_result["file_info"] = {
                    "filename": filename,
                    "content_type": content_type,
                    "size": len(content)
                }
                
                # 2. ADIM: OpenAI Assistant ile skorla
                scoring_result = await openai_assistant_service.score_document(
                    document_analysis=analysis_result,
                    scoring_criteria=scoring_criteria
                )
                
                # Sonucu çıkar
                scoring_data = scoring_result.get("scoring_results", {})
                overall_score = scoring_data.get("overall_score", 0)
                detailed_feedback = scoring_data.get("detailed_feedback", "")
                
                logger.info(f"Tamamlandı: {filename} - Skor: {overall_score}")
                
                return {
                    "success": True,
                    "document_name": filename,
                    "score": overall_score,
                    "detailed_feedback": detailed_feedback,
                    "message": f"Başarıyla skorlandı: {overall_score}/100"
                }
                
            except Exception as e:
                logger.error(f"Dosya işleme hatası ({filename}): {str(e)}")
                return {
                    "success": False,
                    "document_name": filename,
                    "score": 0,
                    "detailed_feedback": "",
                    "error": str(e),
                    "message": f"İşlem başarısız: {str(e)}"
                }
        
        # Tüm dosyaları paralel olarak işle
        logger.info("Paralel işleme başlatılıyor...")
        tasks = [process_single_document(file_data) for file_data in validated_files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Sonuçları işle
        successful_results = []
        failed_results = []
        
        for result in results:
            if isinstance(result, Exception):
                failed_results.append({
                    "success": False,
                    "document_name": "Bilinmeyen",
                    "score": 0,
                    "detailed_feedback": "",
                    "error": str(result),
                    "message": f"İşlem başarısız: {str(result)}"
                })
            elif result.get("success", False):
                successful_results.append(result)
            else:
                failed_results.append(result)
        
        total_files = len(validated_files)
        successful_count = len(successful_results)
        failed_count = len(failed_results)
        
        logger.info(f"Toplu işlem tamamlandı: {successful_count}/{total_files} başarılı")
        
        # Final response
        return {
            "success": True,
            "message": f"{successful_count}/{total_files} dosya başarıyla skorlandı",
            "results": successful_results + failed_results,
            "summary": {
                "total_files": total_files,
                "successful": successful_count,
                "failed": failed_count,
                "success_rate": round((successful_count / total_files) * 100, 2) if total_files > 0 else 0
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Toplu döküman analizi ve skorlama sırasında hata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Toplu işlem başarısız: {str(e)}")

@router.post("/analyze/layout", response_model=Dict[str, Any])
async def analyze_document_layout(
    file: UploadFile = File(..., description="Layout analizi yapılacak belge dosyası")
):
    """
    Yüklenen belgenin layout'unu Azure Document Intelligence ile analiz eder
    
    - **file**: PDF, DOCX, TXT, JPG, PNG formatında belge
    
    Returns:
        - Detaylı layout bilgileri
        - Sayfalar
        - Tablolar
        - Paragraflar
        - Kelimeler
    """
    try:
        logger.info(f"Layout analizi isteği alındı: {file.filename}")
        
        # Dosya tipini kontrol et
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "image/jpeg",
            "image/png",
            "image/tiff"
        ]
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Desteklenmeyen dosya tipi: {file.content_type}"
            )
        
        # Dosyayı oku
        file_content = await file.read()
        
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Boş dosya yüklenemez")
        
        # Layout analizi yap
        layout_result = await document_intelligence_service.analyze_layout(
            document_bytes=file_content,
            content_type=file.content_type
        )
        
        # Dosya bilgilerini ekle
        layout_result["file_info"] = {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(file_content)
        }
        
        logger.info(f"Layout analizi başarıyla tamamlandı: {file.filename}")
        
        return {
            "success": True,
            "message": "Layout analizi başarıyla tamamlandı",
            "data": layout_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Layout analizi sırasında hata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Layout analizi başarısız: {str(e)}")

@router.post("/extract/tables", response_model=Dict[str, Any])
async def extract_tables_from_document(
    file: UploadFile = File(..., description="Tablo çıkarılacak belge dosyası")
):
    """
    Yüklenen belgeden tabloları çıkarır
    
    - **file**: PDF, DOCX, TXT, JPG, PNG formatında belge
    
    Returns:
        - Çıkarılan tablolar
        - Tablo içerikleri
        - Hücre bilgileri
    """
    try:
        logger.info(f"Tablo çıkarma isteği alındı: {file.filename}")
        
        # Dosya tipini kontrol et
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "image/jpeg",
            "image/png",
            "image/tiff"
        ]
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Tablo çıkarma için desteklenmeyen dosya tipi: {file.content_type}"
            )
        
        # Dosyayı oku
        file_content = await file.read()
        
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Boş dosya yüklenemez")
        
        # Tabloları çıkar
        tables = await document_intelligence_service.extract_tables(
            document_bytes=file_content,
            content_type=file.content_type
        )
        
        logger.info(f"Tablo çıkarma başarıyla tamamlandı: {file.filename}, {len(tables)} tablo bulundu")
        
        return {
            "success": True,
            "message": f"{len(tables)} tablo başarıyla çıkarıldı",
            "data": {
                "tables": tables,
                "table_count": len(tables),
                "file_info": {
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "size": len(file_content)
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tablo çıkarma sırasında hata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Tablo çıkarma başarısız: {str(e)}")

@router.post("/analyze/batch", response_model=Dict[str, Any])
async def analyze_multiple_documents(
    files: List[UploadFile] = File(..., description="Analiz edilecek belge dosyaları")
):
    """
    Birden fazla belgeyi toplu olarak analiz eder
    
    - **files**: PDF, DOCX, TXT, JPG, PNG formatında belge listesi
    
    Returns:
        - Her belge için analiz sonuçları
        - Toplu istatistikler
    """
    try:
        logger.info(f"Toplu döküman analizi isteği alındı: {len(files)} dosya")
        
        if len(files) == 0:
            raise HTTPException(status_code=400, detail="En az bir dosya yüklenmeli")
        
        if len(files) > 10:
            raise HTTPException(status_code=400, detail="Maksimum 10 dosya analiz edilebilir")
        
        results = []
        
        for file in files:
            try:
                # Dosya tipini kontrol et
                allowed_types = [
                    "application/pdf",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "text/plain",
                    "image/jpeg",
                    "image/png",
                    "image/tiff"
                ]
                
                if file.content_type not in allowed_types:
                    results.append({
                        "filename": file.filename,
                        "success": False,
                        "error": f"Desteklenmeyen dosya tipi: {file.content_type}"
                    })
                    continue
                
                # Dosyayı oku
                file_content = await file.read()
                
                if len(file_content) == 0:
                    results.append({
                        "filename": file.filename,
                        "success": False,
                        "error": "Boş dosya"
                    })
                    continue
                
                # Analiz et
                analysis_result = await document_intelligence_service.analyze_document(
                    document_bytes=file_content,
                    content_type=file.content_type
                )
                
                analysis_result["file_info"] = {
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "size": len(file_content)
                }
                
                results.append({
                    "filename": file.filename,
                    "success": True,
                    "data": analysis_result
                })
                
            except Exception as e:
                logger.error(f"Dosya analizi başarısız {file.filename}: {str(e)}")
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": str(e)
                })
        
        # İstatistikleri hesapla
        successful_count = sum(1 for r in results if r["success"])
        failed_count = len(results) - successful_count
        
        logger.info(f"Toplu analiz tamamlandı: {successful_count} başarılı, {failed_count} başarısız")
        
        return {
            "success": True,
            "message": f"Toplu analiz tamamlandı: {successful_count}/{len(files)} başarılı",
            "data": {
                "results": results,
                "statistics": {
                    "total_files": len(files),
                    "successful": successful_count,
                    "failed": failed_count,
                    "success_rate": round((successful_count / len(files)) * 100, 2)
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Toplu analiz sırasında hata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Toplu analiz başarısız: {str(e)}")

@router.post("/score", response_model=Dict[str, Any])
async def score_document_analysis(
    document_analysis: Dict[str, Any],
    scoring_criteria: Optional[str] = None
):
    """
    Önceden analiz edilmiş belge verilerini OpenAI Assistant ile skorlar
    
    - **document_analysis**: Azure Document Intelligence'dan gelen analiz sonucu
    - **scoring_criteria**: Özel skorlama kriterleri (opsiyonel)
    
    Returns:
        - AI skorlama sonuçları
        - Detaylı geri bildirim
        - İyileştirme önerileri
        - Güçlü yönler
    """
    try:
        logger.info("Belge skorlama isteği alındı")
        
        if not document_analysis or not isinstance(document_analysis, dict):
            raise HTTPException(
                status_code=400,
                detail="Geçerli bir belge analizi verisi gönderilmeli"
            )
        
        # OpenAI Assistant ile skorla
        scoring_result = await openai_assistant_service.score_document(
            document_analysis=document_analysis,
            scoring_criteria=scoring_criteria
        )
        
        logger.info("Belge skorlama başarıyla tamamlandı")
        
        # Skorlama sonucunu çıkar
        scoring_data = scoring_result.get("scoring_results", {})
        overall_score = scoring_data.get("overall_score", 0)
        detailed_feedback = scoring_data.get("detailed_feedback", "")
        document_name = document_analysis.get("file_info", {}).get("filename", "Bilinmeyen Dosya")
        
        # Sadeleştirilmiş response
        return {
            "success": True,
            "document_name": document_name,
            "score": overall_score,
            "detailed_feedback": detailed_feedback,
            "message": f"{document_name} başarıyla skorlandı: {overall_score}/100"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Belge skorlama sırasında hata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Skorlama başarısız: {str(e)}")



def create_dummy_docx_response(original_filename: str, original_content: bytes) -> bytes:
    """
    Dummy DOCX response oluşturur
    
    Args:
        original_filename: Orijinal dosya adı
        original_content: Orijinal dosya içeriği
        
    Returns:
        bytes: Dummy DOCX dosyası bytes formatında
    """
    try:
        from docx import Document
        from docx.shared import Inches
        
        # Yeni bir Word belgesi oluştur
        doc = Document()
        
        # Başlık ekle
        title = doc.add_heading('İşlenmiş Belge Raporu', 0)
        
        # Paragraf ekle
        doc.add_paragraph(f'Orijinal Dosya: {original_filename}')
        doc.add_paragraph(f'İşleme Tarihi: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}')
        doc.add_paragraph(f'Dosya Boyutu: {len(original_content)} bytes')
        
        doc.add_heading('İşleme Özeti', level=1)
        doc.add_paragraph('Bu belge başarıyla işlenmiştir. Aşağıda işleme detayları bulunmaktadır:')
        
        # Liste ekle
        doc.add_paragraph('• Dosya formatı doğrulandı', style='List Bullet')
        doc.add_paragraph('• İçerik analizi tamamlandı', style='List Bullet')
        doc.add_paragraph('• Kalite kontrol yapıldı', style='List Bullet')
        doc.add_paragraph('• İşleme başarıyla tamamlandı', style='List Bullet')
        
        doc.add_heading('Sonuç', level=1)
        doc.add_paragraph(
            'Belgeniz başarıyla işlenmiştir. Bu dummy response gerçek bir işleme '
            'sürecinin simülasyonudur. Gelecekte bu endpoint gerçek belge işleme '
            'fonksiyonları ile güncellenecektir.'
        )
        
        # Tablo ekle
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Özellik'
        hdr_cells[1].text = 'Değer'
        
        row_cells = table.add_row().cells
        row_cells[0].text = 'Dosya Adı'
        row_cells[1].text = original_filename
        
        row_cells = table.add_row().cells
        row_cells[0].text = 'İşleme Durumu'
        row_cells[1].text = 'Başarılı'
        
        row_cells = table.add_row().cells
        row_cells[0].text = 'İşleme Süresi'
        row_cells[1].text = '< 1 saniye'
        
        # Belgeyi bytes olarak kaydet
        doc_buffer = io.BytesIO()
        doc.save(doc_buffer)
        doc_buffer.seek(0)
        
        return doc_buffer.getvalue()
        
    except ImportError:
        # python-docx yoksa basit bir ZIP dosyası oluştur (minimal DOCX)
        logger.warning("python-docx bulunamadı, basit DOCX oluşturuluyor")
        return create_minimal_docx(original_filename)
    except Exception as e:
        logger.error(f"Dummy DOCX oluşturma hatası: {str(e)}")
        return create_minimal_docx(original_filename)

def create_minimal_docx(filename: str) -> bytes:
    """
    Minimal DOCX dosyası oluşturur (python-docx olmadan)
    """
    import zipfile
    
    # Minimal DOCX yapısı
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''
    
    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p>
            <w:r>
                <w:t>İşlenmiş Belge: {filename}</w:t>
            </w:r>
        </w:p>
        <w:p>
            <w:r>
                <w:t>İşleme Tarihi: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</w:t>
            </w:r>
        </w:p>
        <w:p>
            <w:r>
                <w:t>Bu belge başarıyla işlenmiştir.</w:t>
            </w:r>
        </w:p>
    </w:body>
</w:document>'''
    
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''
    
    # ZIP dosyası oluştur
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('[Content_Types].xml', content_types)
        zip_file.writestr('_rels/.rels', rels)
        zip_file.writestr('word/document.xml', document_xml)
    
    buffer.seek(0)
    return buffer.getvalue()

@router.post("/compare-documents", response_class=HTMLResponse)
async def compare_documents(
    file1: UploadFile = File(..., description="Karşılaştırılacak ilk DOCX belgesi"),
    file2: UploadFile = File(..., description="Karşılaştırılacak ikinci DOCX belgesi")
):
    """
    İki DOCX belgesini Azure Document Intelligence ile analiz eder ve Assistant ile karşılaştırır

    - **file1**: İlk DOCX belgesi
    - **file2**: İkinci DOCX belgesi

    Returns:
        - HTML formatında karşılaştırma tablosu
    """
    try:
        logger.info(f"Belge karşılaştırma isteği alındı: {file1.filename} vs {file2.filename}")

        # Dosya tiplerini kontrol et
        allowed_content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        if file1.content_type != allowed_content_type:
            raise HTTPException(
                status_code=400,
                detail=f"İlk dosya DOCX formatında olmalıdır. Gönderilen tip: {file1.content_type}"
            )

        if file2.content_type != allowed_content_type:
            raise HTTPException(
                status_code=400,
                detail=f"İkinci dosya DOCX formatında olmalıdır. Gönderilen tip: {file2.content_type}"
            )

        # Dosya uzantılarını kontrol et
        if not file1.filename.lower().endswith('.docx'):
            raise HTTPException(status_code=400, detail="İlk dosya .docx uzantısına sahip olmalıdır")

        if not file2.filename.lower().endswith('.docx'):
            raise HTTPException(status_code=400, detail="İkinci dosya .docx uzantısına sahip olmalıdır")

        # Dosyaları oku
        file1_content = await file1.read()
        file2_content = await file2.read()

        if len(file1_content) == 0:
            raise HTTPException(status_code=400, detail="İlk dosya boş olamaz")

        if len(file2_content) == 0:
            raise HTTPException(status_code=400, detail="İkinci dosya boş olamaz")

        # Dosya boyutlarını kontrol et (50MB limit)
        max_file_size = 50 * 1024 * 1024  # 50MB
        if len(file1_content) > max_file_size:
            raise HTTPException(status_code=400, detail="İlk dosya çok büyük (max 50MB)")

        if len(file2_content) > max_file_size:
            raise HTTPException(status_code=400, detail="İkinci dosya çok büyük (max 50MB)")

        logger.info("Dosya validasyonu başarılı, Azure Document Intelligence ile analiz başlatılıyor...")

        # 1. ADIM: Her iki belgeyi Azure Document Intelligence ile analiz et
        analysis1 = await document_intelligence_service.analyze_document(
            document_bytes=file1_content,
            content_type=file1.content_type
        )

        analysis2 = await document_intelligence_service.analyze_document(
            document_bytes=file2_content,
            content_type=file2.content_type
        )

        logger.info("Azure Document Intelligence analizi tamamlandı, Assistant ile karşılaştırma başlatılıyor...")

        # 2. ADIM: İki belgeyi karşılaştırmak için Assistant kullan
        comparison_result = await compare_documents_with_assistant(
            file1.filename, analysis1,
            file2.filename, analysis2
        )

        # 3. ADIM: Assistant response'unu HTML tablosuna dönüştür
        html_table = convert_comparison_to_html_table(
            file1.filename, file2.filename,
            comparison_result, analysis1, analysis2
        )

        logger.info("Belge karşılaştırma başarıyla tamamlandı")

        return HTMLResponse(content=html_table, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Belge karşılaştırma sırasında hata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Karşılaştırma başarısız: {str(e)}")

async def compare_documents_with_assistant(
    filename1: str, analysis1: Dict[str, Any],
    filename2: str, analysis2: Dict[str, Any]
) -> Dict[str, Any]:
    """
    İki belge analizini Assistant ile karşılaştırır
    """
    try:
        # Belge içeriklerini hazırla
        content1 = extract_document_content(filename1, analysis1)
        content2 = extract_document_content(filename2, analysis2)

        # Karşılaştırma prompt'u oluştur
        comparison_prompt = f"""
Lütfen aşağıdaki iki belgeyi detaylı şekilde karşılaştırın:

BELGE 1: {filename1}
{content1}

---

BELGE 2: {filename2}
{content2}

---

KARŞILAŞTIRMA TALEP EDİLEN KONULAR:
1. İçerik Benzerliği: İki belgenin içeriği ne kadar benzer?
2. Yapısal Farklar: Başlık, paragraf, liste yapıları arasındaki farklar
3. Kapsam Karşılaştırması: Hangi konular her iki belgede var, hangisi sadece birinde?
4. Teknik Detaylar: Teknik spesifikasyonlar ve gereksinimler karşılaştırması
5. Kalite Değerlendirmesi: Her iki belgenin kalite açısından karşılaştırması
6. Eksik/Fazla Bölümler: Bir belgede olup diğerinde olmayan bölümler
7. Dil ve Stil: Yazım tarzı ve profesyonellik düzeyi karşılaştırması
8. İki belgenin ayrı ayrı risk detaylarını çıkarın, json formatında olmasın.

LÜTFEN SONUCU ŞU FORMATTA VERİN:
{{
    "overall_similarity": "yüzde_değeri",
    "content_comparison": "detaylı_açıklama",
    "structural_differences": "yapısal_farklar",
    "scope_analysis": "kapsam_analizi",
    "technical_comparison": "teknik_karşılaştırma",
    "quality_assessment": "kalite_değerlendirmesi",
    "missing_sections": "eksik_bölümler",
    "language_style": "dil_stil_karşılaştırma",
    "recommendations": "öneriler",
    "summary": "özet",
    "riskAnalysis": "risk_analizi"

}}
"""

        # Assistant'ı kullan (belirtilen ID ile)
        assistant_id = "asst_ypQ5qVFx9BTAMRLPHusd8MHS"

        # OpenAI service'ini kullan
        from ..services.openai_service import OpenAIService
        openai_service = OpenAIService()

        assistant_response = await openai_service.use_assistant(
            prompt=comparison_prompt,
            assistant_id=assistant_id
        )

        return assistant_response

    except Exception as e:
        logger.error(f"Assistant karşılaştırma hatası: {str(e)}")
        raise Exception(f"Assistant karşılaştırma başarısız: {str(e)}")

def extract_document_content(filename: str, analysis: Dict[str, Any]) -> str:
    """
    Belge analizinden içeriği çıkarır
    """
    content_parts = []

    # Ana içerik
    if "content" in analysis:
        content_parts.append("İÇERİK:")
        content_parts.append(analysis["content"])
        content_parts.append("---")

    # Paragraflar
    if "paragraphs" in analysis and analysis["paragraphs"]:
        content_parts.append("PARAGRAFLAR:")
        for i, para in enumerate(analysis["paragraphs"], 1):
            content_parts.append(f"{i}. {para}")
        content_parts.append("---")

    # Anahtar-değer çiftleri
    if "key_value_pairs" in analysis and analysis["key_value_pairs"]:
        content_parts.append("ANAHTAR BİLGİLER:")
        for kv in analysis["key_value_pairs"]:
            content_parts.append(f"• {kv}")
        content_parts.append("---")

    # Tablolar
    if "tables" in analysis and analysis["tables"]:
        content_parts.append("TABLOLAR:")
        for i, table in enumerate(analysis["tables"], 1):
            content_parts.append(f"Tablo {i}: {table}")
        content_parts.append("---")

    return "\n".join(content_parts)

def convert_comparison_to_html_table(
    filename1: str, filename2: str,
    comparison_result: Dict[str, Any],
    analysis1: Dict[str, Any], analysis2: Dict[str, Any]
) -> str:
    """
    Karşılaştırma sonucunu HTML tablosuna dönüştürür
    """
    try:
        # Assistant response'undan içeriği çıkar
        response_content = comparison_result.get("response", "")

        # JSON formatını bulmaya çalış
        import json
        json_match = re.search(r'\{.*\}', response_content, re.DOTALL)

        if json_match:
            try:
                comparison_data = json.loads(json_match.group())
            except json.JSONDecodeError:
                comparison_data = {
                    "overall_similarity": "Belirsiz",
                    "summary": response_content
                }
        else:
            comparison_data = {
                "overall_similarity": "Belirsiz",
                "summary": response_content
            }

        # HTML template oluştur
        html_content = f"""
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Belge Karşılaştırma Raporu</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2rem;
            margin-bottom: 10px;
        }}
        .header p {{
            margin: 0;
            opacity: 0.9;
        }}
        .content {{
            padding: 30px;
        }}
        .files-info {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .file-card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 20px;
        }}
        .file-card h3 {{
            margin: 0 0 10px 0;
            color: #1e293b;
            font-size: 1.1rem;
        }}
        .file-card p {{
            margin: 5px 0;
            color: #64748b;
            font-size: 0.9rem;
        }}
        .comparison-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .comparison-table th {{
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        .comparison-table td {{
            padding: 15px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: top;
        }}
        .comparison-table tr:last-child td {{
            border-bottom: none;
        }}
        .comparison-table tr:nth-child(even) {{
            background: #f8fafc;
        }}
        .comparison-table tr:hover {{
            background: #f1f5f9;
        }}
        .metric-name {{
            font-weight: 600;
            color: #1e293b;
            width: 200px;
        }}
        .metric-value {{
            color: #374151;
            line-height: 1.5;
        }}
        .similarity-badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9rem;
        }}
        .similarity-high {{
            background: #dcfce7;
            color: #166534;
        }}
        .similarity-medium {{
            background: #fef3c7;
            color: #92400e;
        }}
        .similarity-low {{
            background: #fee2e2;
            color: #991b1b;
        }}
        .timestamp {{
            text-align: center;
            color: #64748b;
            font-size: 0.9rem;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
        }}
        @media (max-width: 768px) {{
            .files-info {{
                grid-template-columns: 1fr;
            }}
            .comparison-table {{
                font-size: 0.9rem;
            }}
            .comparison-table th,
            .comparison-table td {{
                padding: 10px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Belge Karşılaştırma Raporu</h1>
            <p>Azure Document Intelligence & OpenAI Assistant ile oluşturulmuştur</p>
        </div>

        <div class="content">
            <div class="files-info">
                <div class="file-card">
                    <h3>📄 Belge 1</h3>
                    <p><strong>Dosya Adı:</strong> {filename1}</p>
                    <p><strong>Boyut:</strong> {len(analysis1.get('content', ''))} karakter</p>
                    <p><strong>Paragraf Sayısı:</strong> {len(analysis1.get('paragraphs', []))}</p>
                </div>
                <div class="file-card">
                    <h3>📄 Belge 2</h3>
                    <p><strong>Dosya Adı:</strong> {filename2}</p>
                    <p><strong>Boyut:</strong> {len(analysis2.get('content', ''))} karakter</p>
                    <p><strong>Paragraf Sayısı:</strong> {len(analysis2.get('paragraphs', []))}</p>
                </div>
            </div>

            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>Karşılaştırma Kriteri</th>
                        <th>Analiz Sonucu</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td class="metric-name">🎯 Genel Benzerlik</td>
                        <td class="metric-value">
                            <span class="similarity-badge {get_similarity_class(comparison_data.get('overall_similarity', ''))}">{comparison_data.get('overall_similarity', 'Belirsiz')}</span>
                        </td>
                    </tr>
                    <tr>
                        <td class="metric-name">📝 İçerik Karşılaştırması</td>
                        <td class="metric-value">{comparison_data.get('content_comparison', 'Analiz bulunamadı')}</td>
                    </tr>
                    <tr>
                        <td class="metric-name">🏗️ Yapısal Farklar</td>
                        <td class="metric-value">{comparison_data.get('structural_differences', 'Analiz bulunamadı')}</td>
                    </tr>
                    <tr>
                        <td class="metric-name">🔍 Kapsam Analizi</td>
                        <td class="metric-value">{comparison_data.get('scope_analysis', 'Analiz bulunamadı')}</td>
                    </tr>
                    <tr>
                        <td class="metric-name">⚙️ Teknik Karşılaştırma</td>
                        <td class="metric-value">{comparison_data.get('technical_comparison', 'Analiz bulunamadı')}</td>
                    </tr>
                    <tr>
                        <td class="metric-name">⭐ Kalite Değerlendirmesi</td>
                        <td class="metric-value">{comparison_data.get('quality_assessment', 'Analiz bulunamadı')}</td>
                    </tr>
                    <tr>
                        <td class="metric-name">❌ Eksik/Fazla Bölümler</td>
                        <td class="metric-value">{comparison_data.get('missing_sections', 'Analiz bulunamadı')}</td>
                    </tr>
                    <tr>
                        <td class="metric-name">✍️ Dil ve Stil</td>
                        <td class="metric-value">{comparison_data.get('language_style', 'Analiz bulunamadı')}</td>
                    </tr>
                    <tr>
                        <td class="metric-name">💡 Öneriler</td>
                        <td class="metric-value">{comparison_data.get('recommendations', 'Öneri bulunamadı')}</td>
                    </tr>
                    <tr>
                        <td class="metric-name">💡 Risk Raporu</td>
                        <td class="metric-value">{comparison_data.get('riskAnalysis', 'Risk raporu bulunamadı')}</td>
                    </tr>
                    <tr>
                        <td class="metric-name">📋 Özet</td>
                        <td class="metric-value">{comparison_data.get('summary', 'Özet bulunamadı')}</td>
                    </tr>
                </tbody>
            </table>

            <div class="timestamp">
                <p>Rapor Oluşturulma Tarihi: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

        return html_content

    except Exception as e:
        logger.error(f"HTML dönüştürme hatası: {str(e)}")
        return f"""
        <html>
        <body>
            <h1>Karşılaştırma Raporu</h1>
            <p>Belge karşılaştırması tamamlandı ancak rapor oluşturulurken hata oluştu.</p>
            <p>Hata: {str(e)}</p>
            <p>Ham Response: {str(comparison_result)}</p>
        </body>
        </html>
        """

def get_similarity_class(similarity_str: str) -> str:
    """Benzerlik yüzdesine göre CSS sınıfı döndürür"""
    try:
        # Yüzde değerini çıkarmaya çalış
        import re
        match = re.search(r'(\d+)', str(similarity_str))
        if match:
            percentage = int(match.group(1))
            if percentage >= 70:
                return "similarity-high"
            elif percentage >= 40:
                return "similarity-medium"
            else:
                return "similarity-low"
    except:
        pass

    return "similarity-medium"
@router.post("/process-docx")
async def process_docx_file(
    file: UploadFile = File(..., description="İşlenecek DOCX dosyası")
):
    openai_service = OpenAIService()

    text_content = await file_to_string(file)
    process_documents_agent_id = "asst_Bocv8Da8OcjxlyZ9XdowGCC1"
    process_docx_response = await openai_service.use_assistant(
                prompt=f"Aşağıda bir sözleşme metni var. Bu metni analiz et ve bana {agreement_create_schema} formatında, "
        "tüm alanları dolduracak şekilde JSON döndür. Alan başlıklarını ve yapıyı koru, içerikleri metinden çıkar. "
        "Sadece geçerli ve parse edilebilir valid bir JSON döndür. Döndüğün JSON'un başına veya herhangi bir yerine 'json\\n' ifadesini ekleme. "
        "Sözleşme metni:\n\n"
        f"{text_content}",
                assistant_id=process_documents_agent_id
            )
    json_string = process_docx_response.get("response", "")
    json_string = json_string.replace("json\n", "")

    docx_response = agreement_json_to_docx(json_string, output_path="agreement_output.docx")
    buffer = io.BytesIO()
    buffer.seek(0)
    buffer_docx = io.BytesIO()
    docx_response.save(buffer_docx)
    buffer_docx.seek(0)

        # PDF dosyasını döndür
    return Response(
        content=buffer_docx.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename=proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        }
    )

async def process_docx_file(
    file: UploadFile = File(..., description="İşlenecek DOCX dosyası")
    ):
    openai_service = OpenAIService()

    text_content = await file_to_string(file)
    process_documents_agent_id = "asst_Bocv8Da8OcjxlyZ9XdowGCC1"
    process_docx_response = await openai_service.use_assistant(
                prompt=f"Aşağıda bir sözleşme metni var. Bu metni analiz et ve bana {agreement_create_schema} formatında, "
                "tüm alanları dolduracak şekilde JSON döndür. Alan başlıklarını ve yapıyı koru, içerikleri metinden çıkar. "
                "Sadece geçerli ve parse edilebilir JSON döndür. Sözleşme metni:\n\n"
                f"{text_content}",
                assistant_id=process_documents_agent_id
            )
    agreement_json = json.loads(process_docx_response)
    docx_response = agreement_json_to_docx(agreement_json, output_path="agreement_output.docx")
    buffer = io.BytesIO()
    buffer.seek(0)
    buffer_docx = io.BytesIO()
    agreement_json_to_docx.save(buffer_docx)
    buffer_docx.seek(0)

        # PDF dosyasını döndür
    return Response(
        content=buffer_docx.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename=proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        }
    )


agreement_create_schema = """
{
    "contract_title": "Sözleşme Başlığı",
    "date": "25.07.2025",
    "parties": {
        "buyer": "[Alıcı Adı]",
        "supplier": "[Tedarikçi/Satıcı Adı]"
    },
    "sections": [
        {
            "title": "1. Tanımlar ve Taraflar",
            "content": "Tarafların kimlikleri ve sözleşme kapsamındaki rollerini içerir."
        },
        {
            "title": "2. Hizmet/Konu Tanımı",
            "content": "Sözleşmenin konusu, kapsamı ve sağlanacak hizmetler veya ürünler genel olarak açıklanır."
        },
        {
            "title": "3. Süre, Teslimat ve Garanti",
            "content": "Sözleşmenin süresi, teslimat koşulları ve varsa garanti şartları belirtilir."
        },
        {
            "title": "4. Ücretlendirme ve Ödeme",
            "content": "Ücret, ödeme şekli ve takvimi ile ilgili genel bilgiler verilir."
        },
        {
            "title": "5. Fikri Mülkiyet ve Haklar",
            "content": "Sözleşme kapsamında oluşan fikri mülkiyet hakları ve tarafların hakları tanımlanır."
        },
        {
            "title": "6. Yasal Uyum ve Gizlilik",
            "content": "Tarafların yasal yükümlülükleri ve gizlilik hükümleri genel olarak belirtilir."
        },
        {
            "title": "7. Alt Yüklenici ve Üçüncü Taraflar",
            "content": "Alt yüklenici veya üçüncü taraf kullanımı ile ilgili genel hükümler eklenir."
        },
        {
            "title": "8. Riskler ve Fesih",
            "content": "Sözleşmenin feshi, riskler ve kapanış prosedürleri genel olarak tanımlanır."
        },
        {
            "title": "9. Gerekçelendirme Notları",
            "content": "Her madde altında, maddenin sözleşmede yer alma sebebi kısaca açıklanır."
        }
    ],
    "signature_block": {
        "buyer_signature": {
            "title": "Alıcı",
            "company": "[Alıcı Adı]",
            "signature": "_________",
            "stamp": "Kaşe",
            "date": "_/_/2025"
        },
        "supplier_signature": {
            "title": "Tedarikçi/Satıcı",
            "company": "[Tedarikçi/Satıcı Adı]",
            "signature": "_________",
            "stamp": "Kaşe",
            "date": "_/_/2025"
        }
    }
}
"""

async def file_to_string(file: UploadFile) -> str:
    """
    UploadFile objesini string haline getirir.
    TXT dosyaları için decode, DOCX için python-docx ile okuma, PDF için Document Intelligence ile analiz.
    """
    file_content = await file.read()
    if len(file_content) == 0:
        raise HTTPException(status_code=400, detail="Boş dosya işlenemez")

    if file.content_type == "text/plain":
        try:
            return file_content.decode('utf-8')
        except UnicodeDecodeError:
            return file_content.decode('latin-1')

    elif file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from docx import Document
        import io
        doc_stream = io.BytesIO(file_content)
        doc = Document(doc_stream)
        full_text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                full_text.append(paragraph.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        full_text.append(cell.text.strip())
        return "\n".join(full_text)

    elif file.content_type == "application/pdf":
        # PDF için Document Intelligence kullan
        analysis_result = await document_intelligence_service.analyze_document(
            document_bytes=file_content,
            content_type=file.content_type
        )
        content = analysis_result.get("content", "")
        if not content:
            paragraphs = analysis_result.get("paragraphs", [])
            content = "\n".join([p.get("content", "") for p in paragraphs])
        return content

    else:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen dosya tipi: {file.content_type}")

def agreement_json_to_docx(agreement_json: dict, output_path: str = "agreement_output.docx"):
    """
    agreement_create_schema formatındaki JSON'dan DOCX sözleşme oluşturur.
    Args:
        agreement_json: Sözleşme JSON'u (dict)
        output_path: Kaydedilecek DOCX dosya yolu
    Returns:
        docx.Document objesi
    """
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    json_data = json.loads(agreement_json)  # Asistan JSON döndürdüğü için doğrudan parse edilebilir

    # Başlık
    doc.add_heading(json_data.get("contract_title", "Sözleşme"), 0)
    doc.add_paragraph(f"Tarih: {json_data.get('date', '')}")

    # Taraflar
    doc.add_heading("Taraflar", level=1)
    parties = json_data.get("parties", {})
    doc.add_paragraph(f"Alıcı: {parties.get('buyer', '')}")
    doc.add_paragraph(f"Tedarikçi/Satıcı: {parties.get('supplier', '')}")

    # Bölümler
    doc.add_heading("Sözleşme Bölümleri", level=1)
    for section in json_data.get("sections", []):
        doc.add_heading(section.get("title", ""), level=2)
        doc.add_paragraph(section.get("content", ""))

    # İmzalar
    doc.add_heading("İmzalar", level=1)
    signature_block = json_data.get("signature_block", {})
    buyer_sig = signature_block.get("buyer_signature", {})
    supplier_sig = signature_block.get("supplier_signature", {})
    doc.add_paragraph(f"{buyer_sig.get('title', '')}: {buyer_sig.get('company', '')}")
    p_buyer = doc.add_paragraph()
    p_buyer.add_run(f"İmza: {buyer_sig.get('signature', '')} | Kaşe: {buyer_sig.get('stamp', '')} | Tarih: {buyer_sig.get('date', '')}")
    # Kaşe için sadece boşluk bırak
    for _ in range(6):
        doc.add_paragraph("")

    doc.add_paragraph(f"{supplier_sig.get('title', '')}: {supplier_sig.get('company', '')}")
    p_supplier = doc.add_paragraph()
    p_supplier.add_run(f"İmza: {supplier_sig.get('signature', '')} | Kaşe: {supplier_sig.get('stamp', '')} | Tarih: {supplier_sig.get('date', '')}")
    for _ in range(6):
        doc.add_paragraph("")

    doc.save(output_path)
    return doc
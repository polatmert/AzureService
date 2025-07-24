from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
import logging
from typing import List, Dict, Any, Optional
import io

from ..services.document_intelligence_service import document_intelligence_service
from ..services.openai_assistant_service import openai_assistant_service

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
                
                logger.info(f"Tamamlandı: {filename} - Skor: {overall_score}")
                
                return {
                    "success": True,
                    "document_name": filename,
                    "score": overall_score,
                    "message": f"Başarıyla skorlandı: {overall_score}/100"
                }
                
            except Exception as e:
                logger.error(f"Dosya işleme hatası ({filename}): {str(e)}")
                return {
                    "success": False,
                    "document_name": filename,
                    "score": 0,
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
        document_name = document_analysis.get("file_info", {}).get("filename", "Bilinmeyen Dosya")
        
        # Sadeleştirilmiş response
        return {
            "success": True,
            "document_name": document_name,
            "score": overall_score,
            "message": f"{document_name} başarıyla skorlandı: {overall_score}/100"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Belge skorlama sırasında hata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Skorlama başarısız: {str(e)}")

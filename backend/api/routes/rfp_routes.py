from fastapi import APIRouter, HTTPException, Body, Depends, Response
from typing import Dict, Optional
from pydantic import BaseModel
import io
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch

from backend.services.openai_service import OpenAIService
from backend.services.pdf_service import PDFService

# Pydantic modelleri
class AssistantRequest(BaseModel):
    prompt: str
    assistant_id: Optional[str] = None

class ChainAssistantRequest(BaseModel):
    prompt: str
    first_assistant_id: str = "asst_vbaEyelIh7J9g4YhXYXYHIWt"
    second_assistant_id: str = "asst_agqWgdJaUkdGDqkLJWAgRMOl"

router = APIRouter(
    prefix="/rfp",
    tags=["rfp"],
    responses={404: {"description": "Not found"}},
)

@router.post("/ask-assistant")
async def ask_assistant(request: AssistantRequest):
    """
    Azure OpenAI Assistant API'sini kullanarak belirli bir asistana istek gönderir.
    """
    try:
        # OpenAI servisini başlat
        openai_service = OpenAIService()
        
        # Asistana istek gönder
        response = await openai_service.use_assistant(
            prompt=request.prompt,
            assistant_id=request.assistant_id
        )
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    # --- DOSYA SONU ---
from backend.services.rfp_controller import RFPController
rfp_router = RFPController.as_fastapi_router()

@router.post("/chain-assistants")
async def chain_assistants(request: ChainAssistantRequest):
    """
    İki asistanı zincirleyerek çalıştırır. İlk asistanın çıktısı ikinci asistana girdi olarak verilir.
    """
    try:
        # OpenAI servisini başlat
        openai_service = OpenAIService()
        
        # İlk asistana istek gönder
        first_response = await openai_service.use_assistant(
            prompt=request.prompt,
            assistant_id=request.first_assistant_id
        )
        
        if "error" in first_response:
            return first_response
        
        # İlk asistandan gelen yanıtı al
        first_assistant_output = first_response.get("response", "")
        
        # İkinci asistana ilk asistanın yanıtını gönder
        second_response = await openai_service.use_assistant(
            prompt=first_assistant_output,
            assistant_id=request.second_assistant_id
        )
        
        # Sonuçları birleştir
        return {
            "first_assistant": {
                "id": request.first_assistant_id,
                "response": first_assistant_output
            },
            "second_assistant": {
                "id": request.second_assistant_id,
                "response": second_response.get("response", "")
            },
            "original_prompt": request.prompt
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chain-assistants-pdf")
async def chain_assistants_pdf(request: ChainAssistantRequest):
    """
    İki asistanı zincirleyerek çalıştırır ve sonucu PDF olarak döndürür.
    """
    try:
        # OpenAI servisini başlat
        openai_service = OpenAIService()
        
        # İlk asistana istek gönder
        first_response = await openai_service.use_assistant(
            prompt=request.prompt,
            assistant_id=request.first_assistant_id
        )
        
        if "error" in first_response:
            raise HTTPException(status_code=500, detail=first_response.get("error"))
        
        # İlk asistandan gelen yanıtı al
        first_assistant_output = first_response.get("response", "")
        
        # İkinci asistana ilk asistanın yanıtını gönder
        second_response = await openai_service.use_assistant(
            prompt=first_assistant_output,
            assistant_id=request.second_assistant_id
        )
        
        second_assistant_output = second_response.get("response", "")
        
        # PDF oluştur
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # Başlık
        p.setFont("Helvetica-Bold", 16)
        p.drawString(1*inch, 10*inch, "Asistan Yanıtları")
        
        # Orijinal istek
        p.setFont("Helvetica-Bold", 12)
        p.drawString(1*inch, 9.5*inch, "Orijinal İstek:")
        p.setFont("Helvetica", 10)
        
        # Uzun metni satırlara böl
        y_position = 9.3*inch
        lines = wrap_text(request.prompt, 80)
        for line in lines:
            p.drawString(1*inch, y_position, line)
            y_position -= 15
        
        # İlk asistan yanıtı
        y_position -= 20
        p.setFont("Helvetica-Bold", 12)
        p.drawString(1*inch, y_position, f"İlk Asistan Yanıtı (ID: {request.first_assistant_id}):")
        p.setFont("Helvetica", 10)
        
        y_position -= 20
        lines = wrap_text(first_assistant_output, 80)
        for line in lines:
            p.drawString(1*inch, y_position, line)
            y_position -= 15
            if y_position < 1*inch:
                p.showPage()
                y_position = 10*inch
        
        # İkinci asistan yanıtı
        y_position -= 20
        p.setFont("Helvetica-Bold", 12)
        p.drawString(1*inch, y_position, f"İkinci Asistan Yanıtı (ID: {request.second_assistant_id}):")
        p.setFont("Helvetica", 10)
        
        y_position -= 20
        lines = wrap_text(second_assistant_output, 80)
        for line in lines:
            p.drawString(1*inch, y_position, line)
            y_position -= 15
            if y_position < 1*inch:
                p.showPage()
                y_position = 10*inch
        
        p.save()
        
        buffer.seek(0)
        
        # PDF dosyasını döndür
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=assistant_responses.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chain-assistants-azure-pdf")
async def chain_assistants_azure_pdf(request: ChainAssistantRequest):
    """
    İki asistanı zincirleyerek çalıştırır ve sonucu Azure doküman formatında PDF olarak döndürür.
    """
    try:
        # OpenAI servisini başlat
        openai_service = OpenAIService()
        
        # İlk asistana istek gönder
        first_response = await openai_service.use_assistant(
            prompt=request.prompt,
            assistant_id=request.first_assistant_id
        )
        
        if "error" in first_response:
            raise HTTPException(status_code=500, detail=first_response.get("error"))
        
        # İlk asistandan gelen yanıtı al
        first_assistant_output = first_response.get("response", "")
        
        # İkinci asistana ilk asistanın yanıtını gönder
        second_response = await openai_service.use_assistant(
            prompt=first_assistant_output,
            assistant_id=request.second_assistant_id
        )
        
        second_assistant_output = second_response.get("response", "")
        
        # PDF servisini başlat
        pdf_service = PDFService()
        
        # Azure doküman formatında PDF oluştur
        buffer = pdf_service.create_assistant_response_pdf_with_azure_format(
            first_assistant_id=request.first_assistant_id,
            first_response=first_assistant_output,
            second_assistant_id=request.second_assistant_id,
            second_response=second_assistant_output,
            original_prompt=request.prompt
        )
        
        # PDF dosyasını döndür
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=azure_assistant_responses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def wrap_text(text, width):
    """Metni belirli genişlikte satırlara böler."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        if len(' '.join(current_line + [word])) <= width:
            current_line.append(word)
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

@router.get("/assistants")
async def list_assistants():
    """
    Mevcut Assistant'ları listeler.
    """
    try:
        openai_service = OpenAIService()
        response = openai_service.list_assistants()
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/assistants")
async def create_assistant(name: str = "RFP ve Sözleşme Asistanı"):
    """
    Yeni bir Assistant oluşturur.
    """
    try:
        openai_service = OpenAIService()
        response = openai_service.create_assistant(name=name)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
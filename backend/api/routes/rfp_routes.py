from annotated_types import doc
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
from docx import Document
from backend.api.routes.global_storage import global_storage
from backend.services.openai_service import OpenAIService
from backend.services.pdf_service import PDFService
openai_service = OpenAIService()
project_proposal_schema = """
{
  "name": "generate_project_proposal",
  "description": "Generate a project proposal document based on provided information",
  "parameters": {
    "type": "object",
    "properties": {
      "project_name": {
        "type": "string"
      },
      "proposal_due_by": {
        "type": "string",
        "format": "date"
      },
      "company_name": {
        "type": "string"
      },
      "project_overview": {
        "type": "string"
      },
      "project_goals": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "scope_of_work": {
        "type": "string"
      },
      "roadblocks": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "evaluation_criteria": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "submission_requirements": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "project_due_by": {
        "type": "string",
        "format": "date"
      },
      "budget": {
        "type": "string"
      },
      "contact": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "email": {
            "type": "string",
            "format": "email"
          },
          "phone": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "email",
          "phone"
        ]
      }
    },
    "required": [
      "project_name",
      "proposal_due_by",
      "company_name",
      "project_overview",
      "project_goals",
      "scope_of_work",
      "roadblocks",
      "evaluation_criteria",
      "submission_requirements",
      "project_due_by",
      "budget",
      "contact"
    ]
  }
}
"""

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

@router.post("/chain-assistants")
async def chain_assistants(request: ChainAssistantRequest):
    """
    İki asistanı zincirleyerek çalıştırır. İlk asistanın çıktısı ikinci asistana girdi olarak verilir.
    """

    try:
        # OpenAI servisini başlat
        
        
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
            prompt=first_assistant_output + f"Bir yanıt çıktısı almak için {project_proposal_schema} json formatını kullanın. "
            "Çıktı, söz konusu işlev için tanımlanan JSON yapısıyla eşleşmelidir. Tüm json alanlarını kullanın."
            "Yalnızca geçerli JSON argümanlarını döndürün. direkt JSON şeklinde dön string dönme",
            assistant_id=request.second_assistant_id
        )
        json_string = second_response.get("response", "")  # örneğin yukarıdaki gibi gelen içerik
        global_storage.set_second_response(second_response.get("response", ""))

        # Belgeyi oluştur
        json_to_docx2(json_string, "softwareproposal2.docx")

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


            #Bu noktada tekrar n tane sözleşme inputu alacağız 
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
            prompt=first_assistant_output + f"Bir yanıt çıktısı almak için {project_proposal_schema} json formatını kullanın. "
            "Çıktı, söz konusu işlev için tanımlanan JSON yapısıyla eşleşmelidir. Tüm json alanlarını kullanın."
            "Yalnızca geçerli JSON argümanlarını döndürün. direkt JSON şeklinde dön string dönme",
            assistant_id=request.second_assistant_id
        )
        json_string = second_response.get("response", "")  # örneğin yukarıdaki gibi gelen içerik
        global_storage.set_second_response(second_response.get("response", ""))

        # Belgeyi oluştur

       
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
        docx_response = json_to_docx2(json_string, "softwareproposal2.docx")

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
    


import json

def json_to_docx(json_string, output_path) -> Document:

    
    # JSON string'teki kaçış karakterlerini düzelt
    data = json.loads(json_string)

    doc = Document()

    # Başlık
    doc.add_heading("RFP - Teklif Talebi Özeti", level=1)

    doc.add_paragraph(f"📌 Proje Adı: {data['project_name']}")
    doc.add_paragraph(f"📅 Teklif Son Tarihi: {data['proposal_due_by']}")
    doc.add_paragraph(f"🏢 Kurum: {data['company_name']}")

    doc.add_heading("📋 Proje Özeti", level=2)
    doc.add_paragraph(data["project_overview"])

    doc.add_heading("🎯 Proje Amaçları", level=2)
    for goal in data["project_goals"]:
        doc.add_paragraph(f"- {goal}", style="List Bullet")

    doc.add_heading("📦 Kapsam", level=2)
    doc.add_paragraph(data["scope_of_work"])

    doc.add_heading("🚧 Öngörülen Zorluklar", level=2)
    for block in data["roadblocks"]:
        doc.add_paragraph(f"- {block}", style="List Bullet")

    doc.add_heading("🧮 Değerlendirme Kriterleri", level=2)
    for criterion in data["evaluation_criteria"]:
        doc.add_paragraph(f"- {criterion}", style="List Bullet")

    doc.add_heading("📥 Başvuru Gereklilikleri", level=2)
    for req in data["submission_requirements"]:
        doc.add_paragraph(f"- {req}", style="List Bullet")

    doc.add_paragraph(f"📅 Proje Teslim Tarihi: {data['project_due_by']}")
    doc.add_paragraph(f"💰 Bütçe: {data['budget']}")

    doc.add_heading("👤 İletişim", level=2)
    contact = data["contact"]
    doc.add_paragraph(f"İsim: {contact['name']}")
    doc.add_paragraph(f"E-posta: {contact['email']}")
    doc.add_paragraph(f"Telefon: {contact['phone']}")

    doc.save(output_path)
    return doc 
    print(f"✅ DOCX dosyası oluşturuldu: {output_path}")


from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

def json_to_docx2(json_data2: dict, filename: str = "project_proposal.docx") -> Document:  #ÇALIŞAN METOD
    doc = Document()
    json_data = json.loads(json_data2)  # Asistan JSON döndürdüğü için doğrudan parse edilebilir

    def add_heading(text, level=1):
        doc.add_heading(text, level=level)
    
    def add_paragraph(text, bold=False, italic=False):
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.bold = bold
        run.italic = italic
        p.paragraph_format.space_after = Pt(6)
        return p
    
    # Başlık
    doc.add_heading(f"{json_data['project_name']} - Proje Teklifi", 0)
    doc.add_paragraph(f"Şirket: {json_data['company_name']}")
    doc.add_paragraph(f"Teklif Teslim Tarihi: {json_data['proposal_due_by']}")
    doc.add_paragraph(f"Proje Teslim Tarihi: {json_data['project_due_by']}")
    doc.add_paragraph(f"Bütçe: {json_data['budget']}")
    
    doc.add_paragraph("")  # boşluk

    # Genel Bakış
    add_heading("Proje Genel Bakış", level=1)
    add_paragraph(json_data["project_overview"])

    # Hedefler
    add_heading("Proje Hedefleri", level=1)
    for goal in json_data["project_goals"]:
        doc.add_paragraph(f"- {goal}", style='List Bullet')

    # Kapsam
    add_heading("İşin Kapsamı", level=1)
    add_paragraph(json_data["scope_of_work"])

    # Riskler / Engeller
    add_heading("Öngörülen Riskler", level=1)
    for block in json_data["roadblocks"]:
        doc.add_paragraph(f"- {block}", style='List Bullet')

    # Değerlendirme Kriterleri
    add_heading("Değerlendirme Kriterleri", level=1)
    for crit in json_data["evaluation_criteria"]:
        doc.add_paragraph(f"- {crit}", style='List Bullet')

    # Teslimat Gereksinimleri
    add_heading("Teslimat Gereksinimleri", level=1)
    for req in json_data["submission_requirements"]:
        doc.add_paragraph(f"- {req}", style='List Bullet')

    # İletişim Bilgileri
    add_heading("İletişim", level=1)
    contact = json_data["contact"]
    add_paragraph(f"İsim: {contact['name']}")
    add_paragraph(f"E-posta: {contact['email']}")
    add_paragraph(f"Telefon: {contact['phone']}")

    # Kaydet
    doc.save(filename)
    print(f"✓ Kaydedildi: {filename}")
    return doc

from jinja2 import Template
from html2docx import html2docx

def generate_docx_from_json(json_data, template_path, output_docx_path):
    # 1. HTML template dosyasını oku
    data = json.loads(json_data)
    with open(template_path, 'r', encoding='utf-8') as f:
        template_html = f.read()

    # 2. Template'i doldur
    template = Template(template_html)
    rendered_html = template.render(data)

    # 3. HTML'yi .docx'e dönüştür
    html2docx(rendered_html, output_docx_path)
    print(f"✅ DOCX dosyası oluşturuldu: {output_docx_path}")

# Örnek kullanım
if __name__ == "__main__":
    # JSON verisini yükle (dosya da olabilir)
    with open("rfp_data.json", "r", encoding="utf-8") as f:
        json_data = json.load(f)

    generate_docx_from_json(json_data, "template.html", "rfp_output.docx")

"""
@router.post("/compare-documents")
async def chain_assistants(request: ChainAssistantRequest): 
    # Bu noktada tekrar n tane sözleşme inputu alacağız
    # n kere 3. asistanı çağıracağız
    # 3. asistan fayda zarar analizi yapacak ve kaydedecek 

"""

third_assistant_id: str = "asst_agqWgdJaUkdGDqkLJWAgRMOl"

third_assistant_prompt: str = "" #bu asistant 3 kere çağırılacak bizim önceki 
#çıktıya göre bunun kullanılması neden faydalı neden zararlı. Ek olarak bütçe zaman teknoloji analizi yapacak

async def setup_third_assistant(request: ChainAssistantRequest):
    third_response = await openai_service.use_assistant(
                prompt=request.prompt + f"Bu sözelşmeyi önceden oluşturduğum RFD ile karşılaştır. Sektör standarlarındaki uygunluğuna göre ",
                assistant_id=request.third_assistant_id
            )
    


    global_storage.append_json_response(request.prompt,third_response.get("response", ""))


fourth_assistant_id: str = "asst_agqWgdJaUkdGDqkLJWAgRMOl"

fourth_assistant_prompt: str = "" #Bu asistan 3 sözleşmenin verilerini alacak ve bunları karşılaştıracak. aralarından 1 tane seçecek
#ve bu sözleşmeyi öneri olarak verecek.

async def setup_fourth_assistant(request: ChainAssistantRequest):

    best_entry = global_storage.get_highest_scored_json()
    fourth_response = await openai_service.use_assistant(
                prompt=request.prompt + f"{global_storage.get_all_json_responses()} bununla benim için bir sözleşme oluştur",
                assistant_id=request.fourth_assistant_id
            )

    

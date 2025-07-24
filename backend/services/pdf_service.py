import io
import logging
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

logger = logging.getLogger("rfp_app.pdf")

class PDFService:
    """
    PDF oluşturma servisi
    """
    
    def __init__(self):
        """
        PDF servisini başlatır
        """
        self.styles = getSampleStyleSheet()
        
        # Özel stil tanımlamaları - önce kontrol et, sonra ekle
        self._add_custom_style('Title', ParagraphStyle(
            name='Title',
            parent=self.styles['Heading1'],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=12
        ))
        
        self._add_custom_style('Subtitle', ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=10
        ))
        
        self._add_custom_style('Normal', ParagraphStyle(
            name='Normal',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6
        ))
        
        self._add_custom_style('List', ParagraphStyle(
            name='List',
            parent=self.styles['Normal'],
            fontSize=10,
            leftIndent=20,
            spaceAfter=6
        ))
        
        logger.info("PDF servisi başlatıldı")
    
    def _add_custom_style(self, style_name, style_def):
        """
        Stil koleksiyonuna yeni stil ekler, eğer aynı isimde stil varsa üzerine yazmaz
        
        Args:
            style_name: Stil adı
            style_def: Stil tanımı (ParagraphStyle nesnesi)
        """
        if style_name not in self.styles:
            self.styles.add(style_def)
            logger.debug(f"'{style_name}' stili eklendi")
        else:
            logger.debug(f"'{style_name}' stili zaten tanımlı, üzerine yazılmadı")
    
    def create_pdf_from_azure_document(self, document_data, file_id="L714WexQ9BKSNRUyxLETDe"):
        """
        Azure'da yüklü olan doküman formatına göre PDF oluşturur
        
        Args:
            document_data: Doküman verisi (dict formatında)
            file_id: Azure'daki doküman ID'si
            
        Returns:
            BytesIO nesnesi içinde PDF içeriği
        """
        buffer = io.BytesIO()
        
        # PDF dokümanını oluştur
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # İçerik listesi
        content = []
        
        try:
            # Başlık sayfası
            content.append(Paragraph(f"Doküman Referans: {file_id}", self.styles["Normal"]))
            content.append(Spacer(1, 1*cm))
            
            # Logo ekle (eğer varsa)
            if "logo_path" in document_data:
                try:
                    img = Image(document_data["logo_path"], width=5*cm, height=2*cm)
                    content.append(img)
                    content.append(Spacer(1, 0.5*cm))
                except Exception as e:
                    logger.warning(f"Logo yüklenemedi: {e}")
            
            # Başlık ekle
            if "title" in document_data:
                content.append(Paragraph(document_data["title"], self.styles["Title"]))
                content.append(Spacer(1, 0.5*cm))
            
            # Alt başlık ekle
            if "subtitle" in document_data:
                content.append(Paragraph(document_data["subtitle"], self.styles["Subtitle"]))
                content.append(Spacer(1, 0.5*cm))
            
            # Doküman bilgileri
            if "document_info" in document_data:
                info_data = []
                for key, value in document_data["document_info"].items():
                    info_data.append([key, value])
                
                if info_data:
                    t = Table(info_data, colWidths=[4*cm, 12*cm])
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    content.append(t)
                    content.append(Spacer(1, 0.5*cm))
            
            # İçindekiler tablosu
            if "sections" in document_data and isinstance(document_data["sections"], list):
                content.append(Paragraph("İÇİNDEKİLER", self.styles["Subtitle"]))
                
                toc_data = []
                for i, section in enumerate(document_data["sections"]):
                    if "title" in section:
                        toc_data.append([f"{i+1}.", section["title"], f"{i+1}"])
                
                if toc_data:
                    t = Table(toc_data, colWidths=[1*cm, 14*cm, 1*cm])
                    t.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.lightgrey)
                    ]))
                    content.append(t)
                    content.append(Spacer(1, 1*cm))
            
            # Sayfa sonu
            content.append(PageBreak())
            
            # Özet ekle
            if "summary" in document_data:
                content.append(Paragraph("ÖZET", self.styles["Subtitle"]))
                content.append(Paragraph(document_data["summary"], self.styles["Normal"]))
                content.append(Spacer(1, 0.5*cm))
                content.append(PageBreak())
            
            # Bölümler ekle
            if "sections" in document_data and isinstance(document_data["sections"], list):
                for i, section in enumerate(document_data["sections"]):
                    if "title" in section:
                        content.append(Paragraph(f"{i+1}. {section['title']}", self.styles["Subtitle"]))
                    
                    if "content" in section:
                        if isinstance(section["content"], str):
                            content.append(Paragraph(section["content"], self.styles["Normal"]))
                        elif isinstance(section["content"], list):
                            for item in section["content"]:
                                content.append(Paragraph(f"• {item}", self.styles["List"]))
                    
                    # Alt bölümler
                    if "subsections" in section and isinstance(section["subsections"], list):
                        for j, subsection in enumerate(section["subsections"]):
                            if "title" in subsection:
                                content.append(Paragraph(f"{i+1}.{j+1} {subsection['title']}", self.styles["Subtitle"]))
                            
                            if "content" in subsection:
                                if isinstance(subsection["content"], str):
                                    content.append(Paragraph(subsection["content"], self.styles["Normal"]))
                                elif isinstance(subsection["content"], list):
                                    for item in subsection["content"]:
                                        content.append(Paragraph(f"• {item}", self.styles["List"]))
                    
                    # Tablolar
                    if "tables" in section and isinstance(section["tables"], list):
                        for table_data in section["tables"]:
                            if "headers" in table_data and "rows" in table_data:
                                table_content = [table_data["headers"]]
                                table_content.extend(table_data["rows"])
                                
                                t = Table(table_content)
                                t.setStyle(TableStyle([
                                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                                ]))
                                content.append(t)
                                
                                if "caption" in table_data:
                                    # Özel başlık stili
                                    caption_style = ParagraphStyle(
                                        name='Caption',
                                        parent=self.styles['Normal'],
                                        fontSize=8,
                                        alignment=TA_CENTER
                                    )
                                    content.append(Paragraph(f"Tablo {i+1}.{table_data.get('table_number', 1)}: {table_data['caption']}", caption_style))
                    
                    content.append(Spacer(1, 0.5*cm))
                    
                    # Bölüm sonunda sayfa sonu ekle
                    content.append(PageBreak())
            
            # Sonuç ekle
            if "conclusion" in document_data:
                content.append(Paragraph("SONUÇ", self.styles["Subtitle"]))
                content.append(Paragraph(document_data["conclusion"], self.styles["Normal"]))
                content.append(Spacer(1, 0.5*cm))
            
            # Ekler
            if "attachments" in document_data and isinstance(document_data["attachments"], list):
                content.append(Paragraph("EKLER", self.styles["Subtitle"]))
                for i, attachment in enumerate(document_data["attachments"]):
                    content.append(Paragraph(f"Ek {i+1}: {attachment['title']}", self.styles["Normal"]))
                    if "description" in attachment:
                        content.append(Paragraph(attachment["description"], self.styles["Normal"]))
                    content.append(Spacer(1, 0.3*cm))
            
            # PDF oluştur
            doc.build(content)
            buffer.seek(0)
            logger.info("PDF dokümanı başarıyla oluşturuldu")
            
            return buffer
        
        except Exception as e:
            logger.error(f"PDF oluşturma hatası: {e}")
            # Hata durumunda basit bir PDF oluştur
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            p.setFont("Helvetica-Bold", 16)
            p.drawString(2*cm, 27*cm, "PDF Oluşturma Hatası")
            p.setFont("Helvetica", 12)
            p.drawString(2*cm, 26*cm, f"Hata: {str(e)}")
            p.save()
            buffer.seek(0)
            return buffer
    
    def create_assistant_response_pdf_with_azure_format(self, first_assistant_id, first_response, 
                                     second_assistant_id, second_response, original_prompt):
        """
        Asistan yanıtları için Azure doküman formatında PDF oluşturur
        
        Args:
            first_assistant_id: İlk asistan ID'si
            first_response: İlk asistan yanıtı
            second_assistant_id: İkinci asistan ID'si
            second_response: İkinci asistan yanıtı
            original_prompt: Orijinal istek
            
        Returns:
            BytesIO nesnesi içinde PDF içeriği
        """
        # Azure doküman formatına uygun veri yapısı oluştur
        document_data = {
            "title": "Asistan Yanıtları",
            "subtitle": "Zincirlenmiş Asistan Yanıtları",
            "document_info": {
                "Oluşturulma Tarihi": "25.07.2025",
                "Doküman Tipi": "Asistan Yanıtı",
                "İlk Asistan ID": first_assistant_id,
                "İkinci Asistan ID": second_assistant_id
            },
            "summary": f"Bu doküman, kullanıcının '{original_prompt}' isteğine verilen yanıtları içermektedir. " +
                      "İlk asistandan alınan yanıt, ikinci asistana girdi olarak verilmiş ve nihai yanıt oluşturulmuştur.",
            "sections": [
                {
                    "title": "Kullanıcı İsteği",
                    "content": original_prompt
                },
                {
                    "title": "İlk Asistan Yanıtı",
                    "content": first_response,
                    "subsections": [
                        {
                            "title": "Asistan Bilgileri",
                            "content": f"ID: {first_assistant_id}"
                        }
                    ]
                },
                {
                    "title": "İkinci Asistan Yanıtı",
                    "content": second_response,
                    "subsections": [
                        {
                            "title": "Asistan Bilgileri",
                            "content": f"ID: {second_assistant_id}"
                        }
                    ]
                }
            ],
            "conclusion": "Bu yanıtlar, iki asistanın zincirlenmiş çalışması sonucunda oluşturulmuştur. " +
                         "İlk asistan yanıtı ikinci asistana girdi olarak verilmiş ve nihai yanıt oluşturulmuştur."
        }
        
        # Azure doküman formatına uygun PDF oluştur
        return self.create_pdf_from_azure_document(document_data)

# PageBreak sınıfı
class PageBreak:
    def __init__(self):
        pass 

    
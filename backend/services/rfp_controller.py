

import pdfplumber
from typing import List, Union

# Singleton servis örneği
rfp_controller_service = None

def get_rfp_controller_service():
    global rfp_controller_service
    if rfp_controller_service is None:
        rfp_controller_service = RFPController()
    return rfp_controller_service

class RFPController:
    # FastAPI ile kullanılacak örnek servis fonksiyonu
    @staticmethod
    def as_fastapi_router():
        from fastapi import APIRouter, UploadFile, File
        import io
        router = APIRouter()

        @router.post("/rfp/evaluate-pdfs")
        async def evaluate_pdfs(files: List[UploadFile] = File(...)):
            controller = get_rfp_controller_service()
            pdf_buffers = [io.BytesIO(await f.read()) for f in files]
            results = controller.split_and_evaluate_pdfs(pdf_buffers)
            return {"results": results}

        return router
    """
    RFP işlemlerini yöneten controller sınıfı
    """
    def __init__(self):
        pass

    def split_and_evaluate_pdfs(self, pdf_buffers: List[Union[str, bytes]]):
        """
        Liste halinde gelen PDF dosyalarını birer birer ayırır ve değerlendirir.
        Args:
            pdf_buffers: PDF dosyalarının BytesIO, dosya yolu veya bytes listesi
        Returns:
            List[dict]: Her PDF için değerlendirme sonucu
        """
        results = []
        for pdf in pdf_buffers:
            result = self.evaluate_pdf_content(pdf)
            results.append(result)
        return results

    def evaluate_pdf_content(self, pdf_buffer: Union[str, bytes]):
        """
        Tek bir PDF dosyasının içeriğini değerlendirir ve özetler.
        Args:
            pdf_buffer: BytesIO, dosya yolu veya bytes
        Returns:
            dict: Sayfa sayısı, metin içeriği, ilk sayfa metni
        """
        result = {
            "page_count": 0,
            "all_text": "",
            "first_page_text": ""
        }
        with pdfplumber.open(pdf_buffer) as pdf:
            result["page_count"] = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                result["all_text"] += text + "\n"
                if i == 0:
                    result["first_page_text"] = text
        return result

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
import inspect
import logging
import datetime

# Log dosyasını yapılandır
log_filename = f"app_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("rfp_app")
logger.info(f"Uygulama başlatılıyor... Log dosyası: {log_filename}")

# Modül yolunu ekle
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, parent_dir) 

from backend.api.routes import rfp_routes

app = FastAPI(
    title="RFP ve Sözleşme Asistanı",
    description="RFP ve sözleşme hazırlama, analiz ve risk değerlendirme sistemi",
    version="0.1.0"
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Üretim ortamında değiştirilmeli
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sadece RFP rotalarını ekle
app.include_router(rfp_routes.router)

@app.get("/")
def read_root():
    logger.info("Ana sayfa isteği alındı")
    return {"message": "RFP ve Sözleşme Asistanı API'sine Hoş Geldiniz"}

@app.get("/health")
def health_check():
    logger.info("Sağlık kontrolü isteği alındı")
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = 8050
    logger.info(f"Uygulama {port} portunda başlatılıyor...")
    uvicorn.run(app, host="0.0.0.0", port=port) 
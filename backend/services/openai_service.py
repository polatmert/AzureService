import os
import json
import logging
import time
from typing import List, Dict, Any, Optional
from openai import AzureOpenAI, AsyncAzureOpenAI

logger = logging.getLogger("rfp_app.openai")

class OpenAIService:
    """
    Azure OpenAI servisi ile etkileşim için servis sınıfı.
    """
    
    def __init__(
        self, 
        api_key: str = None, 
        model: str = "gpt-4.1"
    ):
        """
        Azure OpenAI servisini başlatır.
        
        Args:
            api_key: Azure OpenAI API anahtarı
            model: Kullanılacak model adı
        """
        # API anahtarını ve endpoint'i doğrudan tanımla
        self.api_key = "FPRujohqESgTY33hn85wMEIYIWuSFVVlvphfgBZ31DXWJdt3n7sIJQQJ99BGACfhMk5XJ3w3AAABACOGJLcR"
        self.model = "gpt-4.1"
        self.assistant_id = None  # Assistant ID'yi None yap, ihtiyaç halinde bulacağız
        self.endpoint = "https://seraph-openapi.openai.azure.com/"
        self.api_version = "2025-01-01-preview"
        
        # API istemcisini oluştur
        try:
            # Standart sohbet tamamlama için istemci
            self.client = AsyncAzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint,
            )
            
            # Senkron istemci (Assistant API için)
            self.sync_client = AzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint
            )
            
            self.is_demo_mode = False
            logger.info(f"Azure OpenAI API bağlantısı kuruldu. Model: {self.model}, Endpoint: {self.endpoint}")
            
            # Assistant ID'sini initialize et
            self._initialize_assistant()
            
        except Exception as e:
            logger.error(f"Azure OpenAI API bağlantısı kurulamadı: {e}")
            self.is_demo_mode = True
            logger.warning("Demo moduna geçiliyor...")
    
    def _initialize_assistant(self):
        """
        Assistant'ı initialize eder. Mevcut olanları listeler veya yeni bir tane oluşturur.
        """
        try:
            # Önce mevcut Assistant'ları listele
            assistants = self.sync_client.beta.assistants.list()
            
            if assistants.data:
                # İlk mevcut Assistant'ı kullan
                self.assistant_id = assistants.data[0].id
                logger.info(f"Mevcut Assistant kullanılacak: {self.assistant_id}")
                logger.info(f"Assistant adı: {assistants.data[0].name}")
                
        except Exception as e:
            logger.error(f"Assistant initialize hatası: {e}")
            logger.warning("Assistant olmadan devam edilecek...")
            self.assistant_id = None
    
    async def use_assistant(self, prompt: str, assistant_id: str = None) -> Dict[str, Any]:
        """
        Azure OpenAI Assistant API'sini kullanarak belirli bir asistana istek gönderir.
        
        Args:
            prompt: Kullanıcı isteği
            assistant_id: Kullanılacak asistan ID'si (belirtilmezse varsayılan kullanılır)
            
        Returns:
            Asistan yanıtı
        """
        if self.is_demo_mode:
            logger.info(f"Demo modunda asistan yanıtı oluşturuluyor...")
            return {
                "response": "Bu bir demo yanıttır. Gerçek Azure OpenAI Assistant API'sine bağlantı kurulamadı.",
                "assistant_id": assistant_id or self.assistant_id
            }
        
        # Asistan ID'sini belirle
        assistant_id = assistant_id or self.assistant_id
        
        # Eğer assistant_id yoksa direkt chat completion kullan
        if not assistant_id:
            logger.info("Assistant ID bulunamadı, chat completion API kullanılıyor")
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Sen bir RFP ve sözleşme uzmanısın. Dokümanları analiz etme, risk değerlendirme, şablon oluşturma konularında uzmansın. Türkçe yanıt ver."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=4000
                )
                
                return {
                    "response": response.choices[0].message.content,
                    "method": "chat_completion",
                    "model": response.model,
                    "tokens": response.usage.total_tokens
                }
            except Exception as e:
                logger.error(f"Chat completion API hatası: {e}")
                return {"error": f"Chat completion API hatası: {str(e)}"}
        
        try:
            logger.info(f"Azure OpenAI Assistant API'ye istek gönderiliyor... Assistant ID: {assistant_id}")
            
            # Thread oluştur
            thread = self.sync_client.beta.threads.create()
            logger.info(f"Thread oluşturuldu: {thread.id}")
            
            # Mesajı thread'e ekle
            message = self.sync_client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=prompt
            )
            logger.info(f"Mesaj thread'e eklendi: {message.id}")
            
            # Assistant'ı çalıştır
            run = self.sync_client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant_id
            )
            logger.info(f"Assistant çalıştırıldı: {run.id}")
            
            # Run'ın tamamlanmasını bekle
            while run.status in ['queued', 'in_progress', 'cancelling']:
                time.sleep(1)
                run = self.sync_client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                logger.info(f"Run durumu: {run.status}")
            
            if run.status == 'completed':
                # Mesajları al
                messages = self.sync_client.beta.threads.messages.list(
                    thread_id=thread.id
                )
                
                # En son assistant mesajını bul
                assistant_message = None
                for msg in messages.data:
                    if msg.role == "assistant":
                        assistant_message = msg
                        break
                
                if assistant_message:
                    response_text = assistant_message.content[0].text.value
                    logger.info(f"Assistant yanıtı alındı: {len(response_text)} karakter")
                    
                    return {
                        "response": response_text,
                        "assistant_id": assistant_id,
                        "thread_id": thread.id,
                        "run_id": run.id
                    }
                else:
                    logger.error("Assistant mesajı bulunamadı")
                    return {"error": "Assistant mesajı bulunamadı"}
            else:
                logger.error(f"Run başarısız oldu: {run.status}")
                if run.last_error:
                    logger.error(f"Hata detayı: {run.last_error}")
                return {"error": f"Run başarısız: {run.status}"}
            
        except Exception as e:
            logger.error(f"Azure OpenAI Assistant API hatası: {str(e)}")
            logger.error(f"Hata detayları: {type(e).__name__}")
            
            # Fallback: Chat completion API kullan
            try:
                logger.info("Fallback: Chat completion API kullanılıyor")
                
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": f"Sen Azure OpenAI'da tanımlı bir asistansın. ID: {assistant_id}. Kullanıcının isteğini en iyi şekilde yanıtla."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=4000
                )
                
                return {
                    "response": response.choices[0].message.content,
                    "assistant_id": assistant_id,
                    "note": "Assistant API hatası nedeniyle chat completion API kullanıldı",
                    "fallback": True
                }
            except Exception as e2:
                logger.error(f"Fallback yöntemi de başarısız oldu: {str(e2)}")
                return {
                    "error": f"Assistant API hatası: {str(e)}. Fallback hatası: {str(e2)}",
                    "assistant_id": assistant_id
                }
    
    async def analyze_document(self, content: str, analysis_type: List[str], document_type: str) -> Dict[str, Any]:
        """
        Dokümanı analiz eder.
        
        Args:
            content: Doküman içeriği
            analysis_type: Analiz türleri listesi
            document_type: Doküman türü (rfp, contract, vb.)
            
        Returns:
            Analiz sonuçları
        """
        if self.is_demo_mode:
            # Demo modunda analiz simülasyonu
            logger.info(f"Demo modunda {document_type} analizi yapılıyor")
            if document_type == "rfp":
                return {
                    "completeness": {
                        "score": 85,
                        "missing_sections": ["SLA tanimlari", "Test kriterleri"],
                        "recommendations": ["SLA bolumunu detaylandirin", "Test kriterlerini ekleyin"]
                    },
                    "clarity": {
                        "score": 78,
                        "unclear_sections": ["Teknik gereksinimler", "Teslimat takvimi"],
                        "recommendations": ["Teknik gereksinimleri daha acik tanimlayin"]
                    },
                    "risks": {
                        "high": ["Veri gizliligi maddeleri eksik", "KVKK uyumlulugu belirtilmemis"],
                        "medium": ["Cezai sartlar tek tarafli tanimlanmis"],
                        "low": ["Proje yonetim metodolojisi belirsiz"]
                    }
                }
            elif document_type == "contract":
                return {
                    "legal": {
                        "compliance": {
                            "kvkk": False,
                            "gdpr": False,
                            "recommendations": ["KVKK uyum maddesi ekleyin", "Veri isleme maddeleri yetersiz"]
                        },
                        "intellectual_property": {
                            "status": "incomplete",
                            "recommendations": ["Fikri mulkiyet haklari net degil"]
                        }
                    },
                    "risks": {
                        "high": ["Fesih kosullari belirsiz", "Teslim kriterleri tanimsiz"],
                        "medium": ["Garanti suresi belirtilmemis"],
                        "low": ["Destek kosullari detaylandirilmamis"]
                    },
                    "balance": {
                        "status": "unbalanced",
                        "issues": ["Cezai sartlar tek tarafli", "Iptal kosullari dengesiz"],
                        "recommendations": ["Karsilikli ceza maddeleri ekleyin"]
                    }
                }
            else:
                return {"error": "Desteklenmeyen dokuman turu"}
        
        # Gerçek Azure OpenAI analizi
        system_prompt = self._get_system_prompt(document_type, analysis_type)
        user_prompt = f"Lutfen asagidaki dokumani analiz et:\n\n{content}"
        
        try:
            logger.info(f"Azure OpenAI API'ye analiz isteği gönderiliyor... Model: {self.model}")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            logger.info(f"Azure OpenAI API'den yanıt alındı: {response.model}")
            logger.info(f"Kullanılan token sayısı: {response.usage.total_tokens}")
            result = json.loads(response.choices[0].message.content)
            logger.info("Yanıt başarıyla JSON'a dönüştürüldü.")
            return result
        except Exception as e:
            logger.error(f"Azure OpenAI API hatası: {e}")
            # Hata durumunda demo modu yanıtlarını kullan
            logger.warning("Demo modu yanıtlarına geçiliyor...")
            return await self.analyze_document(content, analysis_type, document_type)
    
    async def compare_documents(self, old_content: str, new_content: str) -> Dict[str, Any]:
        """
        İki dokümanı karşılaştırır.
        
        Args:
            old_content: Eski doküman içeriği
            new_content: Yeni doküman içeriği
            
        Returns:
            Karşılaştırma sonuçları
        """
        if self.is_demo_mode:
            # Demo modunda karşılaştırma simülasyonu
            logger.info("Demo modunda doküman karşılaştırması yapılıyor")
            return {
                "differences": [
                    {
                        "section": "Odeme Kosullari",
                        "old_text": "Odeme 30 gun icinde yapilacaktir.",
                        "new_text": "Odeme 45 gun icinde yapilacaktir.",
                        "significance": "medium"
                    },
                    {
                        "section": "Teslimat Suresi",
                        "old_text": "Proje 6 ay icinde tamamlanacaktir.",
                        "new_text": "Proje 8 ay icinde tamamlanacaktir.",
                        "significance": "high"
                    }
                ]
            }
        
        # Gerçek Azure OpenAI karşılaştırması
        system_prompt = """
        Sen bir dokuman karsilastirma uzmanisin. Iki dokuman versiyonu arasindaki farklari tespit etmen gerekiyor.
        Lutfen asagidaki formatta JSON ciktisi ver:
        
        {
            "differences": [
                {
                    "section": "Bolum adi",
                    "old_text": "Eski metin",
                    "new_text": "Yeni metin",
                    "significance": "low/medium/high"
                }
            ]
        }
        
        Onem derecesini (significance) belirlerken:
        - "high": Onemli hukuki, mali veya proje zaman cizelgesi degisiklikleri
        - "medium": Orta derecede onemli degisiklikler
        - "low": Kucuk, daha cok dilbilgisi veya bicimlendirme degisiklikleri
        """
        
        user_prompt = f"""
        Lutfen asagidaki iki dokumani karsilastir ve farklari tespit et:
        
        ESKI DOKUMAN:
        {old_content}
        
        YENI DOKUMAN:
        {new_content}
        """
        
        try:
            logger.info("Azure OpenAI API'ye karşılaştırma isteği gönderiliyor...")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            logger.info(f"Azure OpenAI API'den karşılaştırma yanıtı alındı: {response.model}")
            logger.info(f"Kullanılan token sayısı: {response.usage.total_tokens}")
            result = json.loads(response.choices[0].message.content)
            logger.info("Karşılaştırma yanıtı başarıyla JSON'a dönüştürüldü.")
            return result
        except Exception as e:
            logger.error(f"Azure OpenAI API hatası: {e}")
            # Hata durumunda demo modu yanıtlarını kullan
            logger.warning("Demo modu yanıtlarına geçiliyor...")
            return {
                "differences": [
                    {
                        "section": "Odeme Kosullari",
                        "old_text": "Odeme 30 gun icinde yapilacaktir.",
                        "new_text": "Odeme 45 gun icinde yapilacaktir.",
                        "significance": "medium"
                    },
                    {
                        "section": "Teslimat Suresi",
                        "old_text": "Proje 6 ay icinde tamamlanacaktir.",
                        "new_text": "Proje 8 ay icinde tamamlanacaktir.",
                        "significance": "high"
                    }
                ]
            }
    
    async def generate_template(self, template_type: str, industry: Optional[str] = None) -> Dict[str, Any]:
        """
        Belirli bir şablon türü için içerik oluşturur.
        
        Args:
            template_type: Şablon türü (rfp, contract, vb.)
            industry: Endüstri/sektör
            
        Returns:
            Oluşturulan şablon
        """
        if self.is_demo_mode:
            # Demo modunda şablon oluşturma simülasyonu
            logger.info(f"Demo modunda {template_type} şablonu oluşturuluyor. Endüstri: {industry or 'Belirtilmemiş'}")
            if template_type == "rfp":
                return {
                    "title": "Yazilim Gelistirme RFP Sablonu",
                    "sections": [
                        {
                            "title": "Proje Ozeti",
                            "content": "Bu bolumde projenin genel amacini ve kapsamini tanimlayiniz."
                        },
                        {
                            "title": "Teknik Gereksinimler",
                            "content": "Bu bolumde projenin teknik gereksinimlerini detaylandiriniz."
                        },
                        {
                            "title": "Zaman Cizelgesi",
                            "content": "Bu bolumde projenin zaman cizelgesini ve onemli kilometre taslarini belirtiniz."
                        }
                    ]
                }
            elif template_type == "contract":
                return {
                    "title": "Yazilim Gelistirme Sozlesmesi",
                    "sections": [
                        {
                            "title": "Taraflar",
                            "content": "Bu bolumde sozlesmenin taraflarini tanimlayiniz."
                        },
                        {
                            "title": "Kapsam ve Hizmetler",
                            "content": "Bu bolumde verilecek hizmetlerin kapsamini tanimlayiniz."
                        },
                        {
                            "title": "Odeme Kosullari",
                            "content": "Bu bolumde odeme planini ve kosullarini belirtiniz."
                        },
                        {
                            "title": "Fikri Mulkiyet Haklari",
                            "content": "Bu bolumde yazilimin fikri mulkiyet haklarini tanimlayiniz."
                        }
                    ]
                }
            else:
                return {"error": "Desteklenmeyen sablon turu"}
        
        # Gerçek Azure OpenAI şablon oluşturma
        industry_text = f" {industry} sektoru icin" if industry else ""
        
        system_prompt = f"""
        Sen bir {template_type.upper()} dokumani hazirlama uzmanisin.{industry_text} Lutfen asagidaki formatta JSON ciktisi ver:
        
        {{
            "title": "Sablon basligi",
            "sections": [
                {{
                    "title": "Bolum basligi",
                    "content": "Bolum icerigi ve aciklamasi"
                }}
            ]
        }}
        """
        
        user_prompt = f"Lutfen bir {template_type.upper()}{industry_text} sablonu olustur."
        
        try:
            logger.info(f"Azure OpenAI API'ye şablon oluşturma isteği gönderiliyor... Endüstri: {industry or 'Belirtilmemiş'}")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            logger.info(f"Azure OpenAI API'den şablon yanıtı alındı: {response.model}")
            logger.info(f"Kullanılan token sayısı: {response.usage.total_tokens}")
            result = json.loads(response.choices[0].message.content)
            logger.info("Şablon yanıtı başarıyla JSON'a dönüştürüldü.")
            logger.info(f"Oluşturulan şablon bölümleri: {len(result.get('sections', []))}")
            return result
        except Exception as e:
            logger.error(f"Azure OpenAI API hatası: {e}")
            # Hata durumunda demo modu yanıtlarını kullan
            logger.warning("Demo modu yanıtlarına geçiliyor...")
            if template_type == "rfp":
                return {
                    "title": "Yazilim Gelistirme RFP Sablonu",
                    "sections": [
                        {
                            "title": "Proje Ozeti",
                            "content": "Bu bolumde projenin genel amacini ve kapsamini tanimlayiniz."
                        },
                        {
                            "title": "Teknik Gereksinimler",
                            "content": "Bu bolumde projenin teknik gereksinimlerini detaylandiriniz."
                        },
                        {
                            "title": "Zaman Cizelgesi",
                            "content": "Bu bolumde projenin zaman cizelgesini ve onemli kilometre taslarini belirtiniz."
                        }
                    ]
                }
            else:
                return {"error": "API hatasi nedeniyle sablon olusturulamadi"}
    
    def create_thread(self) -> Dict[str, Any]:
        """
        Yeni bir thread oluşturur.
        
        Returns:
            Thread bilgileri
        """
        try:
            thread = self.sync_client.beta.threads.create()
            logger.info(f"Yeni thread oluşturuldu: {thread.id}")
            return {"thread_id": thread.id, "success": True}
        except Exception as e:
            logger.error(f"Thread oluşturma hatası: {e}")
            return {"error": str(e), "success": False}
    
    def add_message_to_thread(self, thread_id: str, content: str, role: str = "user") -> Dict[str, Any]:
        """
        Bir thread'e mesaj ekler.
        
        Args:
            thread_id: Thread ID'si
            content: Mesaj içeriği
            role: Mesaj rolü (user/assistant)
            
        Returns:
            Mesaj bilgileri
        """
        try:
            message = self.sync_client.beta.threads.messages.create(
                thread_id=thread_id,
                role=role,
                content=content
            )
            logger.info(f"Mesaj thread'e eklendi: {message.id}")
            return {"message_id": message.id, "success": True}
        except Exception as e:
            logger.error(f"Mesaj ekleme hatası: {e}")
            return {"error": str(e), "success": False}
    
    def get_thread_messages(self, thread_id: str) -> Dict[str, Any]:
        """
        Bir thread'in mesajlarını getirir.
        
        Args:
            thread_id: Thread ID'si
            
        Returns:
            Thread mesajları
        """
        try:
            messages = self.sync_client.beta.threads.messages.list(thread_id=thread_id)
            message_list = []
            for msg in messages.data:
                message_list.append({
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content[0].text.value if msg.content else "",
                    "created_at": msg.created_at
                })
            
            return {"messages": message_list, "success": True}
        except Exception as e:
            logger.error(f"Mesajları getirme hatası: {e}")
            return {"error": str(e), "success": False}
    
    def list_assistants(self) -> Dict[str, Any]:
        """
        Mevcut Assistant'ları listeler.
        
        Returns:
            Assistant listesi
        """
        try:
            assistants = self.sync_client.beta.assistants.list()
            assistant_list = []
            for assistant in assistants.data:
                assistant_list.append({
                    "id": assistant.id,
                    "name": assistant.name,
                    "model": assistant.model,
                    "instructions": assistant.instructions,
                    "created_at": assistant.created_at
                })
            
            logger.info(f"{len(assistant_list)} Assistant bulundu")
            return {"assistants": assistant_list, "count": len(assistant_list), "success": True}
        except Exception as e:
            logger.error(f"Assistant listeleme hatası: {e}")
            return {"error": str(e), "success": False}
    
    def create_assistant(self, name: str = "RFP ve Sözleşme Asistanı", instructions: str = None) -> Dict[str, Any]:
        """
        Yeni bir Assistant oluşturur.
        
        Args:
            name: Assistant adı
            instructions: Assistant talimatları
            
        Returns:
            Oluşturulan Assistant bilgileri
        """
        if not instructions:
            instructions = "Sen bir RFP (Request for Proposal) ve sözleşme uzmanısın. Dokümanları analiz etme, risk değerlendirme, şablon oluşturma konularında uzmansın. Türkçe yanıt ver."
        
        try:
            assistant = self.sync_client.beta.assistants.create(
                name=name,
                instructions=instructions,
                model=self.model
            )
            
            logger.info(f"Yeni Assistant oluşturuldu: {assistant.id}")
            return {
                "assistant_id": assistant.id,
                "name": assistant.name,
                "model": assistant.model,
                "success": True
            }
        except Exception as e:
            logger.error(f"Assistant oluşturma hatası: {e}")
            return {"error": str(e), "success": False}
    
    def _get_system_prompt(self, document_type: str, analysis_type: List[str]) -> str:
        """
        Doküman türüne ve analiz türüne göre sistem promptu oluşturur.
        
        Args:
            document_type: Doküman türü
            analysis_type: Analiz türleri listesi
            
        Returns:
            Oluşturulan sistem promptu
        """
        base_prompt = f"""
        Sen bir {document_type.upper()} dokumani analiz uzmanisin. 
        Verilen dokumani inceleyerek asagidaki alanlarda analiz yapmalisin:
        """
        
        analysis_prompts = {
            "completeness": """
            - completeness: Dokumanda eksik bolumler var mi? Hangi onemli bilgiler eksik?
              * score: 0-100 arasi bir tamamlanma puani
              * missing_sections: Eksik bolumler listesi
              * recommendations: Eksiklikleri gidermek icin oneriler
            """,
            
            "clarity": """
            - clarity: Dokumandaki ifadeler ne kadar net ve anlasilir?
              * score: 0-100 arasi bir netlik puani
              * unclear_sections: Net olmayan bolumler listesi
              * recommendations: Netlestirme onerileri
            """,
            
            "risks": """
            - risks: Dokumanda risk olusturabilecek maddeler nelerdir?
              * high: Yuksek riskli maddeler listesi
              * medium: Orta riskli maddeler listesi
              * low: Dusuk riskli maddeler listesi
            """,
            
            "legal": """
            - legal: Dokumanda yasal uyumluluk sorunlari var mi?
              * compliance: KVKK, GDPR gibi yasal duzenlemelere uyum durumu
              * intellectual_property: Fikri mulkiyet haklari tanimlamalari
              * recommendations: Yasal uyumluluk onerileri
            """,
            
            "balance": """
            - balance: Dokuman taraflar arasinda dengeli mi?
              * status: "balanced" veya "unbalanced"
              * issues: Dengesizlik yaratan maddeler
              * recommendations: Denge saglama onerileri
            """
        }
        
        for analysis in analysis_type:
            if analysis in analysis_prompts:
                base_prompt += analysis_prompts[analysis]
        
        base_prompt += """
        Lutfen analiz sonuclarini JSON formatinda don. Ornek:
        
        {
          "completeness": {
            "score": 85,
            "missing_sections": ["SLA tanimlari", "Test kriterleri"],
            "recommendations": ["SLA bolumunu detaylandirin", "Test kriterlerini ekleyin"]
          },
          "clarity": {
            "score": 78,
            "unclear_sections": ["Teknik gereksinimler", "Teslimat takvimi"],
            "recommendations": ["Teknik gereksinimleri daha acik tanimlayin"]
          }
        }
        
        Sadece istenen analiz turlerini cevaba dahil et.
        """
        
        return base_prompt 
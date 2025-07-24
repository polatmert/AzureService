class JsonResponseEntry:
    """JSON response için struct sınıfı"""
    def __init__(self, json_data: str, score: float = 0.0):
        self.json_data = json_data
        self.score = score
        from datetime import datetime
        self.timestamp = datetime.now().isoformat()
        
    def to_dict(self):
        """Dict formatına çevir"""
        return {
            "json_data": self.json_data,
            "score": self.score,
            "timestamp": self.timestamp
        }

class GlobalStorage:
    _instance = None
    _second_response = None
    _json_responses = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def set_second_response(self, response: str):
        self._second_response = response
    
    def get_second_response(self) -> str:
        return self._second_response or ""
    
    def clear_second_response(self):
        self._second_response = None

    def append_json_response(self, json_data: str, score: float = 0.0, max_count: int = 100):
        """
        JSON response'u struct ile birlikte listeye ekler.
        
        Args:
            json_data: Eklenecek JSON string
            score: JSON için puan (varsayılan 0.0)
            max_count: Maksimum tutulacak response sayısı
        """
        response_entry = JsonResponseEntry(json_data, score)
        self._json_responses.append(response_entry)
    
    def get_all_json_responses(self) -> list:
        """Tüm JSON response'ları döndürür."""
        return self._json_responses
    def clear_all_json_responses(self):
        """Tüm JSON response'ları temizler."""
        self._json_responses = []
    def get_json_responses_count(self) -> int:
            """Toplam JSON response sayısını döndürür."""
            return len(self._json_responses)
    

    def get_highest_scored_json(self) -> JsonResponseEntry:
        """
        En yüksek skorlu JSON objesini döndürür.
        
        Returns:
            En yüksek skorlu JsonResponseEntry objesi, liste boşsa None
        """
        if not self._json_responses:
            return None
        
        # En yüksek skorlu objeyi bul ve JsonResponseEntry olarak döndür
        highest_entry = max(self._json_responses, key=lambda entry: entry.score)
        return highest_entry
    
# Global instance
global_storage = GlobalStorage()
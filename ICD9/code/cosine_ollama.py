from sentence_transformers import SentenceTransformer, CrossEncoder
import numpy as np
import pickle
from modules.icd9_base_matcher import *
from modules.ollama import get_prompt_result

class CosineLLMICD9Matcher(ICD9_BaseMatcher):
    def __init__(self, embeddings_path="data/icd9_embeddings.pkl"):
        super().__init__(embeddings_path)
    
    def use_bielik(self):
        self.model_name = "SpeakLeash/bielik-11b-v2.2-instruct:Q4_K_M"
    
    def use_pllum(self):
        self.model_name = "hf.co/NikolayKozloff/PLLuM-12B-instruct-Q5_K_M-GGUF:latest"

    def match(self, query_text, top_k=5, **kwargs):
        top_k = 100
        query_emb = self.model.encode([query_text], normalize_embeddings=True)
        similarities = (query_emb @ self.embeddings.T)[0]
        
        
        # Indeksy najlepszych kandydatów do re-rankingu
        candidate_indices = np.argsort(similarities)[-top_k:][::-1]
        
        # 3. Etap 2: Cross-Encoder (Re-ranking)
        
        text = ""
        for i, idx in enumerate(candidate_indices):
            text += f"{self.codes[idx]} - {self.descriptions[idx]}.\n"
        
        prompt = f"""Na podstawie opisu pacjenta dopasuj maksymalnie pasujące kody ICD-9.
Bądź precyzyjny, nie wychodź poza listę kodów.
Bardzo ważne: jako wynik zwróć tylko i wyłącznie JSON array posortowany od najlepszego dopasowania, zawierający:
{{{{ "icd9": "kod", "desc": "opis" }}}}

Nie wyjaśniaj, zwróć czysty JSON otoczony ```.

##Opis pacjenta do analizy:
{query_text}

##Lista kodów do dopasowania:
{text}
"""
        res = get_prompt_result(prompt,model=self.model_name)
        return {"raw":res}

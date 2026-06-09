from sentence_transformers import SentenceTransformer, CrossEncoder
import numpy as np
import pickle
from modules.icd9_base_matcher import *

class CosineCrossICD9Matcher(ICD9_BaseMatcher):
    def __init__(self, embeddings_path="data/icd9_embeddings.pkl"):
        super().__init__(embeddings_path)        
        # Cross-Encoder (Wolniejszy, ale bardzo precyzyjny - do ostatecznej oceny)
        self.bi_encoder = self.model
        self.cross_encoder = CrossEncoder("radlab/polish-cross-encoder")        
        print(f"OK: System gotowy. Cross-Encoder załadowany.")

    def match(self, query_text, top_k=5, **kwargs):
        rerank_depth = kwargs.get("rerank_depth", 40)
        # 1. Wstępne czyszczenie (opcjonalnie, ale pomaga)
        # query_text = clean_medical_query(query_text) 

        # 2. Etap 1: Bi-Encoder (wybierz 20-30 potencjalnych kandydatów)
        query_emb = self.bi_encoder.encode([query_text], normalize_embeddings=True)
        similarities = (query_emb @ self.embeddings.T)[0]
        
        # Indeksy najlepszych kandydatów do re-rankingu
        candidate_indices = np.argsort(similarities)[-rerank_depth:][::-1]
        
        # 3. Etap 2: Cross-Encoder (Re-ranking)
        # Tworzymy pary [Zapytanie, Opis procedury]
        pairs = [[query_text, self.descriptions[idx]] for idx in candidate_indices]
        
        text = ""
        for i, idx in enumerate(candidate_indices):
            text += f"{self.codes[idx]} - {self.descriptions[idx]}.\n"
        
        # Cross-encoder zwraca wyniki (zazwyczaj logity lub prawdopodobieństwo)
        cross_scores = self.cross_encoder.predict(pairs)
        
        # 4. Łączenie i sortowanie wyników
        final_results = []
        for i, idx in enumerate(candidate_indices):
            final_results.append({
                'icd9': self.codes[idx],
                'description': self.descriptions[idx],
                'cross_score': float(cross_scores[i]),  #czy sa znormalizowane? NIE
                'score': float(similarities[idx]) #czy sa znormalizowane? TAK /to wynik cosinus/
            })
        
        # Sortujemy według oceny Cross-Encodera (najważniejsza)
        final_results = sorted(final_results, key=lambda x: x['cross_score'], reverse=True)
        
        return final_results[:top_k]


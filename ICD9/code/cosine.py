from sentence_transformers import SentenceTransformer
import numpy as np
import pandas as pd
import pickle
from modules.icd9_base_matcher import *
                             
class CosineICD9Matcher(ICD9_BaseMatcher):
    def __init__(self, embeddings_path="data/icd9_embeddings.pkl"):
        super().__init__(embeddings_path)
    
    def _normalize_similarity(self, sim: float) -> float:
        # cosine in [-1, 1] -> [0, 1]
        return (sim + 1.0) / 2.0

    def match(self, query_text, top_k=5, **kwargs):
        """
        Dopasuj opis badania do ICD-9 używając Silver-Retriever
        
        Args:
            query_text: Pełny opis badania
            top_k: Liczba wyników
            threshold: Min cosine similarity (Silver-Retriever: 0.6 = dobry próg)
        """
        # Query embedding z normalizacją
        query_emb = self.model.encode(
            [query_text], 
            normalize_embeddings=True
        )
        threshold = kwargs.get('threshold', 0.60)
        
        # Cosine similarity (już znormalizowane = dot product!)
        similarities = (query_emb @ self.embeddings.T)[0]
        
        # Top-k indices
        
        top_indices = np.argsort(similarities)[-top_k*2:][::-1]
        
        results = []
        for idx in top_indices:
            
            sim = float(similarities[idx])
            if sim > threshold:
                results.append({
                    'icd9': self.codes[idx],
                    'description': self.descriptions[idx],
                    'score': self._normalize_similarity(sim),
                    'confidence': self._get_confidence(sim)
                })
        
        return results[:top_k]
    
    def _get_confidence(self, sim):
        """Silver-Retriever calibrated thresholds"""
        if sim > 0.80: return 'very_high'
        if sim > 0.70: return 'high'
        if sim > 0.60: return 'medium'
        return 'low'
    
    # def batch_match(self, query_texts, top_k=5):
    #     """Batch processing dla benchmarku"""
    #     query_embs = self.model.encode(
    #         query_texts,
    #         batch_size=64,
    #         show_progress_bar=True,
    #         normalize_embeddings=True
    #     )
        
    #     # Szybki batch cosine
    #     all_sims = query_embs @ self.embeddings.T  # [N, 14k]
        
    #     all_results = []
    #     for sims in all_sims:
    #         top_idx = np.argsort(sims)[-top_k:][::-1]
    #         results = [{
    #             'kod': self.codes[i],
    #             'similarity': float(sims[i])
    #         } for i in top_idx]
    #         all_results.append(results)
        
    #     return all_results


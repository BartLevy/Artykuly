from abc import ABC, abstractmethod
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import pickle
                             
class ICD9_BaseMatcher:
    def __init__(self, embeddings_path="data/icd9_embeddings.pkl"):
        with open(embeddings_path, "rb") as f:
            data = pickle.load(f)
        
        self.embeddings = data['embeddings']  # [14k, 768]
        self.codes = np.array(data['codes'])
        self.descriptions = data['descriptions']
        self.model = SentenceTransformer("ipipan/silver-retriever-base-v1")
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        self.embeddings = self.embeddings / np.clip(norms, 1e-12, None)
        
    @abstractmethod
    def match(self, query_text, top_k=5, **kwargs):
        pass
        

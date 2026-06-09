from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import pickle
from modules.helper import save_json_file

def train_and_save():
    # 1. Load data
    df_icd9 = pd.read_excel("data/icd-9_pl_cm__v_5.80.xlsx")
    
    # 2. Clean - Use regex to catch whitespace, then fillna
    df_icd9 = df_icd9.replace(r'^\s*$', np.nan, regex=True)
    
    # Apply your logic: Fill subcategory (6) with category (4)
    # Apply your logic: Fill subcode (7) with code (5)
    df_icd9.iloc[:, 6] = df_icd9.iloc[:, 6].fillna(df_icd9.iloc[:, 4])
    df_icd9.iloc[:, 7] = df_icd9.iloc[:, 7].fillna(df_icd9.iloc[:, 5])

    # 3. Extract lists - Ensure they are strings to avoid model errors
    # Verify if 6 is code and 7 is description or vice versa!
    codes = df_icd9.iloc[:, 6].astype(str).tolist() 
    descriptions = df_icd9.iloc[:, 7].astype(str).tolist()
    save_json_file("temp_descriptions.json", descriptions)
    save_json_file("temp_codes.json", codes)
    

    # 4. Initialize Model
    model = SentenceTransformer("ipipan/silver-retriever-base-v1")

    print("Generuję embeddings...")
    icd9_embeddings = model.encode(
        descriptions,
        batch_size=32, # Lower batch size is safer for consumer GPUs/RAM
        show_progress_bar=True,
        convert_to_numpy=True
    )

    # 5. Save with metadata
    save_data = {
        'embeddings': icd9_embeddings,
        'codes': codes,
        'descriptions': descriptions
    }
    
    with open("data/icd9_embeddings.pkl", "wb") as f:
        pickle.dump(save_data, f)

    print(f"Success! Saved {icd9_embeddings.shape[0]} vectors.")

train_and_save()
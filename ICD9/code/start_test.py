import sys, os
from sentence_transformers import SentenceTransformer, CrossEncoder
import numpy as np
import time
import random
from modules.icd9_base_matcher import *
from cosine_cross import *
from cosine import *
from cosine_ollama import *
from modules.helper import load_json_file, save_json_file



# x = load_json_file("data/generated-full.json")
# y = []
# i = 0
# while (len(y)<500):
#     possible = 0.4
#     if ("rtg" in x[i]["desc"].lower()): possible = 1
#     if ("tk " in x[i]["desc"].lower()): possible = 1
#     print(random.random())
#     i += 1
#     if (possible==1 or random.random()<possible): 
#         y.append(x[i])
# save_json_file("data/generated.json", y)
# print("transfered", len(y))
# exit(0)

## === Config ===
display_results = False
matcher_name="cosine" #cosine ; cosine_cross ; bielik ; pllum
matcher = None

## === Test ===
if (matcher_name=="cosine"): matcher = CosineICD9Matcher()
if (matcher_name=="cosine_cross"): matcher = CosineCrossICD9Matcher()
if (matcher_name=="bielik"): 
    matcher = CosineLLMICD9Matcher()
    matcher.use_bielik()
    matcher.match("test zero shot", top_k=8)
if (matcher_name=="pllum"): 
    matcher = CosineLLMICD9Matcher()
    matcher.use_pllum()
    matcher.match("test zero shot", top_k=8)

med_data = load_json_file("data/generated.json")

idx = 0
for med in med_data:
    print(idx," of ", len(med_data), end="\r")
    # query = """Pacjent 49-letni z przewlekłym bólem nadbrzusza.
    # Wykonano USG jamy brzusznej - badanie ultrasonograficzne 
    # wykazało powiększoną śledzionę 150x90mm."""
    query = med["desc"]
    start = time.perf_counter()
    results = matcher.match(query, top_k=8)
    end = time.perf_counter()
    # print((end - start) * 1000.0)
    results = {
        "matches": results,
        "time_ms": int((end - start) * 1000) 
    }
        
    med["matcher_" + matcher_name] = results
    
    
    save_json_file("data/generated.json", med_data)
    
    # if display_results:
    #     if (matcher_name in ["cosine","cosine_cross"]):
    #         for i, r in enumerate(results, 1):
    #             print(f"{i}. ICD-9: {r['icd9']}")
    #             print(f"   Procedura: {r['description']}")
    #             print(f"   Similarity: {r['score']:.4f}\n")

    #     if (matcher_name in ["bielik","pllum"]):
    #         print(results)
    idx += 1
print("done!")
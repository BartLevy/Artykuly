import os, sys, subprocess
import random
import requests
import json
from modules.helper import *


def get_icd9(data):
    # 0 = Option 1 (70%), 1 = Option 2 (20%), 2 = Option 3 (10%)
    n = random.choices([1, 2, 3], weights=[70, 22, 8], k=1)[0]
    indices = random.sample(range(len(data)), n)
    res = []
    for i in indices:
        res.append(data[i])    
    return res

def get_icd10(data):
    res = []
    n = random.choices([0, 1, 2, 3 , 4], weights=[40, 30, 20, 7, 3], k=1)[0]
    if (n==0): return res
    indices = random.sample(range(len(data)), n)    
    for i in indices:
        res.append(data[i])    
    return res

def get_prompt_result(prompt, model, url):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False 
    }

    try:
        #print("curl",url, "-d", "'" + json.dumps(payload) +"'")
        response = requests.post(url, json=payload)
        response.raise_for_status()
        txt = response.json()['response'].strip()      
        return txt
    except Exception as e:
        print(f"Błąd API: {e}")
        return None     

#Body    
ollama_url = "http://127.0.0.1:11434/api/generate"
ollama_model = "gemma3:27b"#SpeakLeash/bielik-11b-v2.2-instruct:Q4_K_M"
generated = load_json_file("data/generated.json", [])
possible_icd9 = load_json_file("data/popular-er-icd9.json")
comorbidities = load_json_file("data/comorbidities.json")

for i in range(10000):
    print("processing idx",i)
    icd9_arr = get_icd9(possible_icd9)
    icd10_arr =  get_icd10(comorbidities)
    ic9 = " ".join(x["code"] for x in icd9_arr)
    icd10 = " ".join(x["icd10"] for x in icd10_arr)
    age = random.randrange(17, 90)
    gender = random.choices(["kobieta", "mężczyzna"])[0]

    prompt = f"""
    Rola: Jesteś doświadczonym lekarzem specjalistą, który sporządza dokumentację medyczną w systemie HIS.

    Zadanie: Na podstawie podanych kodów ICD-9 (procedury) i opcjonalnie ICD-10 (diagnozy), wygeneruj realistyczny, zanonimizowany opis badania przedmiotowego (fizykalnego) oraz przebiegu procedury/badania.
    Dane wejściowe:
    - Płeć: {gender}
    - Wiek: {age}
    - Kody ICD-9 (kluczowe): {ic9}
    - Kody ICD-10 (opcjonalne): {icd10}

    Wytyczne dla opisu:
    - Naturalny język medyczny: Używaj profesjonalnego żargonu, skrótów medycznych (np. RR, akcja serca miarowa, brzuch miękki, bez objawów otrzewnowych).
    - Kontekst ICD-9: Opis musi logicznie uzasadniać wykonanie procedur z kodów ICD-9. Jeśli kodem jest "88.76 - USG jamy brzusznej", opis musi zawierać powód skierowania (np. ból w nadbrzuszu) oraz techniczny opis wyniku badania.
    Struktura:
    - Wywiad i badanie przedmiotowe: Krótki opis stanu pacjenta przy przyjęciu/badaniu.
    - Opis procedury/badania: Szczegółowy przebieg czynności odpowiadający kodom ICD-9.
    - Zmienność: Nie generuj zawsze idealnych wyników. Czasem opisz patologię, a czasem stan prawidłowy, zależnie od kontekstu kodów.

    Format wyjściowy: Zwróć tekst w formie ciągłej, przypominającej notatkę lekarską z systemu. W odpowiedzi nie podawaj kodów ICD, podawaj tyko czysty opis.
    """


    res = get_prompt_result(prompt, ollama_model, ollama_url)
    if (res!=None):
        generated.append({"desc":res,"gender" : gender, "age" : age, "icd9" : icd9_arr, "icd10" : icd10_arr})
        save_json_file("data/generated.json", generated)
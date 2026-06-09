import requests, json

def get_prompt_result(prompt, 
                    model = "SpeakLeash/bielik-11b-v2.2-instruct:Q4_K_M",
                    url = "http://localhost:11434/api/generate",
                    num_ctx=8192,
                    temperature=0.1):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False ,
        "options": {
            "num_ctx": num_ctx,
            "temperature": temperature
        }
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        txt = response.json()['response'].strip()      
        return txt
    except Exception as e:
        print(f"Błąd API: {e}")
        return None     
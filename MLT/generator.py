import math
from itertools import combinations
import hashlib
import json
from pydub import AudioSegment

def ilosc_komb(n,k):
    return math.factorial(n) / (math.factorial(k) * math.factorial(n - k))

def create_empty(): 
    sound_index = []
    sound_index.append("background")
    return AudioSegment.from_file("background.mp3"), sound_index

def overlay(source, sound_to_add):
    sound_to_add = sound_to_add + ".mp3"
    sound2 = AudioSegment.from_file(sound_to_add)
    combined = source.overlay(sound2, loop=True)
    #combined.export("tmp.mp3", format='mp3')
    return combined

def save(audiofile, sound_set):
    tmp = ''.join( sound_set )
    fname = hashlib.md5(tmp.encode()).hexdigest() + "" 
    audiofile.export("out/"+fname + ".mp3", format='mp3')
    return fname
    
#print(hashlib.md5(b'GeeksforGeeks').digest())

l = ["chicken",
"cow",
"dog",
"donkey",
"elephant",
"frog",
"horse",
"monkey"]
#"sheep","lion",
meta_data = []
idx = 0
for i in range(0,len(l)):
    cmbs = (list(combinations(l, i + 1) ))
    
    for jingle_set in cmbs:
        idx = idx + 1
        print("Generating set ",idx)
        sound, sounds_index = create_empty()
        for jingle in jingle_set:            
            sounds_index.append(str(jingle))
            sound = overlay(sound, str(jingle))
            
        meta_data.append({"fname":save(sound, sounds_index),"set":sounds_index,"num_sounds_without_noise": len(sounds_index)-1})
        #print( meta_data )


with open('meta.json', 'w') as output:
    output.write(json.dumps(meta_data))

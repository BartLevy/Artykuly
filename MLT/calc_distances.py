import os, sys, json, math, random
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import itertools

class CalcDist:
    
    def __init__(self):
        self.frame = []
    def load_data(self, input_file):
        with open(input_file,"r", encoding="utf-8") as f: 
            self.data = json.loads(f.read())
        return self.get_data()
    
    def get_dist(self, a,b):
        x = abs(a["pc1"] - b["pc1"])
        y = abs(a["pc2"] - b["pc2"])
        d = math.sqrt(x*x + y*y)
        d = abs(d)
        return d
    
    def clear_frame(self):
        self.frame = []
    
    def set_frame(self, frame):
        self.frame = frame
        
    def add_to_frame(self, d):
        if (self.frame==None): self.clear_frame()
        self.frame.append(d)
    
    def get_frame_dist(self):
        dist = 0
        min_dist = 99999999
        for a in self.frame:
            for b in self.frame:
                tmp = self.get_dist(a,b)
                dist += tmp
                if (tmp>0 and tmp < min_dist): min_dist = tmp
        return dist, min_dist
    
    def get_frame(self):
        return self.frame
    
    def get_data(self):
        return self.data
"""
def display(data, out_file):
    pc1 = [d['pc1'] for d in data]
    pc2 = [d['pc2'] for d in data]
    names = [d['n'] for d in data]

    plt.figure(figsize=(10, 10))
    scatter = plt.scatter(pc1, pc2, s=150, alpha=0.8, c=range(len(data)), cmap='tab10')

    # **Inteligentne pozycje etykiet**
    offsets = [(10, 10), (-10, 20), (10, -20), (-10, -10), 
               (15, 5), (-15, 5), (15, -5), (-15, -5)]
    
    for i, name in enumerate(names):
        short_name = name[:12] + '...' if len(name) > 12 else name
        offset = offsets[i % len(offsets)]  # Cykl przez offsety
        
        plt.annotate(short_name, (pc1[i], pc2[i]), 
                    xytext=offset, textcoords='offset points', 
                    fontsize=9, ha='center', fontweight='bold',
                    bbox=dict(boxstyle="round,pad=0.1", facecolor='white', alpha=0.8,
                             edgecolor='gray', linewidth=0.5))

    plt.xlim(-1.1, 1.1)
    plt.ylim(-1.1, 1.1)
    plt.gca().set_aspect('equal')
    plt.grid(True, alpha=0.3)
    plt.xlabel('PC1')
    plt.ylabel('PC2')
    plt.tight_layout()
    #plt.show()
    plt.savefig(out_file , dpi=200)
    plt.close()
"""

def display(frames, out_file):
   
    plt.figure(figsize=(10, 10))

    offsets = [(10, 10), (-10, 20), (10, -20), (-10, -10),
               (15, 5), (-15, 5), (15, -5), (-15, -5)]

    # Kolor per ramka (row)
    cmap = plt.get_cmap("tab10")

    for row_i, data in enumerate(frames):
        #pc1 = [d["pc1"] for d in data]
        pc1 = [d["pc1"] for d in data if "pc1" in d]
        #pc2 = [d["pc2"] for d in data]
        pc2 = [d["pc2"] for d in data if "pc2" in d]
        names = [d["n"] for d in data if "n" in d]

        color = cmap(row_i % cmap.N)

        # jeden kolor dla całej ramki
        plt.scatter(pc1, pc2, s=150, alpha=0.8, color=color)

        # etykiety
        for i, name in enumerate(names):
            short_name = name[:12] + "..." if len(name) > 12 else name
            offset = offsets[i % len(offsets)]
            plt.annotate(
                short_name, (pc1[i], pc2[i]),
                xytext=offset, textcoords="offset points",
                fontsize=9, ha="center", fontweight="bold",
                bbox=dict(
                    boxstyle="round,pad=0.1",
                    facecolor="white", alpha=0.8,
                    edgecolor="gray", linewidth=0.5
                )
            )

    plt.xlim(-1.1, 1.1)
    plt.ylim(-1.1, 1.1)
    plt.gca().set_aspect("equal")
    plt.grid(True, alpha=0.3)
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.tight_layout()
    plt.savefig(out_file, dpi=200)
    plt.close()

def save_data(out_file, data):    
    with open(out_file,"w", encoding="utf-8") as f: 
        itx = 0
        for frame in data:
            itx += 1
            names = [d["n"] for d in frame if "n" in d]
            line = ", ".join(names) +";\n"
            f.write(f"{itx}. {line}")

        
dist = CalcDist()
data = dist.load_data("set.json")


for set_size in range(2,9):
    frames_min = []
    frames_max = []

    print("iterating set", set_size)
    for frame in itertools.combinations(data, set_size):
        frame = list(frame)    
        dist.set_frame(frame)    
        val, local_min = dist.get_frame_dist()
        frame.append({"dist" : val/2 })
        frame.append({"local_min" : local_min })        
        frames_min.append(frame)
        if local_min>0.4:
            frames_max.append(frame)

    print("sorting")
    frames_min.sort(key=lambda x: x[set_size]["dist"])
    frames_max.sort(key=lambda x: x[set_size]["dist"])
    top = frames_min[:3]
    bottom = frames_max[-3:]
    display(top[:1],f"out_rep/mins_{set_size}.png")
    display(bottom[-1:],f"out_rep/maxes_{set_size}.png")
    save_data(f"out_rep/mins_{set_size}.txt", top)
    save_data(f"out_rep/maxes_{set_size}.txt", bottom)

exit()

min_frame = []
max_frame = []
min_dist = 99999999999999
max_dist = 0

for i in range(0,20000):
    print(i, end="\r")
    dist.clear_frame()
    frame = random.sample(data, 8)    
    dist.set_frame(frame)    
    val, local_min = dist.get_frame_dist()
    #print(val, local_min)
    if (val < min_dist):
        min_dist = val
        min_frame = dist.get_frame()
    
    if (val > max_dist and local_min>0.4):
        max_dist = val
        max_frame = dist.get_frame()

print("\nmin", min_dist)
print(min_frame)
print("\nmax",max_dist)
print(max_frame)

display(min_frame,"mins.png")
display(max_frame,"maxes.png")
        
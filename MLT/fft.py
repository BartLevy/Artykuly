import json
import os, glob
import numpy as np
import librosa
from infi_reports import InfiReports
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from sklearn.decomposition import PCA
from sklearn.metrics import pairwise_distances
from infi_reports import InfiReports
import pandas as pd

from pydub import AudioSegment

original = ["chicken",  "donkey" ,"horse" , "sheep" ,"cow","elephant","lion", "dog","frog","monkey"
]

def mp3_to_wav(mp3_path, wav_path="temp.wav"):
    # Convert MP3 to WAV format for librosa compatibility
    audio = AudioSegment.from_mp3(mp3_path)
    audio.export(wav_path, format="wav")
    return wav_path

def calculate_spectral_centroid(audio_path):
    # Load audio file with librosa
    y, sr = librosa.load(audio_path)
    #print(f"Sampling rate (sr): {sr} Hz")  # Check sample rate
    
    duration = librosa.get_duration(y=y, sr=sr)
    # Calculate spectral centroids for each frame
    spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    
    # Calculate global centroid as the mean of frame centroids
    global_centroid = np.mean(spectral_centroids)
    
    # Print debugging information for spectral centroid values
    #print(f"Spectral centroids (first 10): {spectral_centroids[:10]}")
    print(f"{audio_path:<15}{duration:>6.2f}{global_centroid:>10.2f}")
    
    return spectral_centroids, global_centroid


def calculate_par(y):
    """Oblicza Współczynnik Szczytowy Amplitudy (PAR) w dB."""
    # Obliczanie Poziomu Szczytowego (Peak)
    peak_amplitude = np.max(np.abs(y))
    # Dodanie epsilon, aby uniknąć log(0)
    peak_level_db = 20 * np.log10(peak_amplitude + np.finfo(float).eps) 
    
    # Obliczanie Średniego Poziomu Skutecznego (RMS)
    rms_amplitude = np.sqrt(np.mean(y**2))
    rms_level_db = 20 * np.log10(rms_amplitude + np.finfo(float).eps)
    
    # PAR = Peak - RMS
    par_db = peak_level_db - rms_level_db
    print(rms_amplitude, rms_level_db, "##", par_db)
    return par_db

def normalize_file_audio_name(name):    
    return name.replace("article/","").replace(".mp3","")

def analyze_audio_features(audio_path, n_mfcc=13, report = None):
    """
    Ładuje plik audio i oblicza: Spectral Centroid, MFCC (uśrednione), PAR, F0 (średnie).    
    """
    try:
        # Load audio file with librosa
        # sr=None zachowuje oryginalną częstotliwość próbkowania pliku
        y, sr = librosa.load(audio_path, sr=None)
        
        duration = librosa.get_duration(y=y, sr=sr)
        
        # --- 1. Spectral Centroid ---
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        global_centroid = np.mean(spectral_centroids)
        
        # --- 2. MFCC (Mel-Frequency Cepstral Coefficients) ---
        # Obliczanie macierzy MFCC (n_mfcc x liczba ramek)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
        # Uśrednianie wzdłuż osi czasu, aby otrzymać jeden wektor cech (1 x n_mfcc)
        mean_mfcc_vector = np.mean(mfccs, axis=1)
        
        # --- 3. F0 (Fundamental Frequency / Pitch) ---
        # Używamy pitenet, która zwraca macierz pitch-ów i ich pewności
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        
        # Ekstrakcja F0:
        # Znajdujemy F0 dla każdej ramki o najwyższej pewności (magnitudes)
        # Pamiętaj, że librosa piptrack zwraca wartości zera dla ciszy lub szumu
        f0_values = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            f0 = pitches[index, t]
            if f0 > 0:  # Ignoruj zero (cisza/szum)
                f0_values.append(f0)
        
        # Obliczanie średniej F0 tylko dla ramek z wykrytym dźwiękiem
        global_f0 = np.mean(f0_values) if f0_values else 0.0
        
        # --- 4. PAR (Peak-to-Average Ratio) ---
        par_db = calculate_par(y)
        
        # --- Wynik i Debugging ---
        print(f"--- Analiza Pliku: {audio_path} ---")
        print(f"Długość: {duration:.2f} s")
        print(f"1. Centroid Widmowy (Globalny): {global_centroid:.2f} Hz")
        print(f"2. F0 (Średnia Podstawowa Częstotliwość): {global_f0:.2f} Hz")
        print(f"3. PAR (Dynamika): {par_db:.2f} dB")
        print(f"4. MFCC (Uśrednione, {n_mfcc} cech): {mean_mfcc_vector}")
        
        data = {
            'name' : normalize_file_audio_name( audio_path),
            'duration' : duration,
            'centroid': global_centroid,
            'mfcc': mean_mfcc_vector,
            'par': par_db,
            'f0': global_f0
        }
        
        return data

    except Exception as e:
        print(f"Wystąpił błąd podczas przetwarzania {audio_path}: {e}")
        return None

################ charts
def draw_chart(data, report):
    global original
    names = [ d["name"]  for d in data]

    feature_rows = []
    for d in data:
        # wektor: [centroid, f0, par, mfcc_1..mfcc_13]
        row = np.concatenate((
            np.array([d["centroid"], d["f0"], d["par"]]),
            d["mfcc"]
        ))
        feature_rows.append(row)

    X = np.vstack(feature_rows)   # shape: (N, 16)

    print("Kształt macierzy cech:", X.shape)

    # =============================
    # 3. NORMALIZACJA 0–1
    # =============================

    scaler = MinMaxScaler()
    X_norm = scaler.fit_transform(X)

    # =============================
    # 4. PCA 16D → 2D
    # =============================

    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_norm)

    plt.figure(figsize=(10, 10))
    plt.scatter(X_pca[:, 0], X_pca[:, 1])

    offsets = [(10, 10), (-10, 20), (10, -20), (-10, -10), 
               (15, 5), (-15, 5), (15, -5), (-15, -5)]
    for i, name in enumerate(names):
        offset = offsets[i % len(offsets)]  # Cykl przez offsety
        #plt.text(X_pca[i, 0] + offset[0]/500, X_pca[i, 1] + offset[1]/500, name, fontsize=6)
        plt.annotate(name, (X_pca[i, 0], X_pca[i, 1]), 
                    xytext=offset, textcoords='offset points', 
                    fontsize=9, ha='center', fontweight='bold',
                    bbox=dict(boxstyle="round,pad=0.1", facecolor="palegreen" if name in original else "skyblue", alpha=0.8,
                             edgecolor='black' if name in original else 'gray', linewidth=1.5 if name in original else 0.5))
        
    
    
    all = []
    
    for i, name in enumerate(names):
        # print(X_pca[i, 0], X_pca[i, 1])
        all.append({"n" : name, "pc1" : float(X_pca[i, 0]), "pc2" : float(X_pca[i, 1])})
    with open("set.json","w", encoding="utf-8") as f: f.write(json.dumps(all))
    

    # To pokaże wagę każdej z 16 cech dla PC1 i PC2
    loadings = pd.DataFrame(pca.components_.T, columns=['PC1', 'PC2'], 
                            index=['Centroid', 'F0', 'PAR'] + [f'MFCC_{i}' for i in range(1, 14)])
    # print(loadings)
    
    plt.title("PCA 2D – znormalizowane wektory audio")
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("images/pca_normas.png", dpi=400)
    plt.close()

    # =============================
    # 5. MACIERZ ODLEGŁOŚCI EUKLIDESOWYCH + HEATMAPA
    # =============================

    D = pairwise_distances(X_norm, metric='euclidean')

    plt.figure(figsize=(6, 5))
    im = plt.imshow(D, interpolation='nearest')
    plt.colorbar(im, label="Odległość euklidesowa")

    plt.xticks(range(len(names)), names, rotation=45)
    plt.yticks(range(len(names)), names)

    plt.title("Macierz odległości euklidesowych (po normalizacji)")

    # (opcjonalnie) numery w komórkach
    for i in range(len(names)):
        for j in range(len(names)):
            plt.text(j, i, f"{D[i, j]:.2f}",
                    ha="center", va="center", fontsize=8)

    #plt.tight_layout()
    #plt.show()
    plt.savefig("pca_plot.png", dpi=200)
    plt.close()



### load save
def save_features(path, data):
    json_ready = []

    for item in data:
        json_item = {
            "name": item["name"],
            "centroid": float(item["centroid"]),
            "f0": float(item["f0"]),
            "par": float(item["par"]),
            "mfcc": item["mfcc"].tolist()
        }
        json_ready.append(json_item)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(json_ready, f, ensure_ascii=False, indent=2)


def load_features(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    data = []
    for item in raw:
        obj = {
            "name": item["name"],
            "centroid": np.float32(item["centroid"]),
            "f0": np.float32(item["f0"]),
            "par": np.float32(item["par"]),
            "mfcc": np.array(item["mfcc"], dtype=np.float32)
        }
        data.append(obj)

    return data




##############################
def process_local(report):
    data = []
    #mp3_files = glob.iglob('article/*.mp3', recursive=False)
    mp3_files = [f for f in glob.iglob('article/*.mp3')]
    #x = sum(1 for _ in mp3_files)
    #print(x)
    report.add_h1("Materiał i metody")
    
    local_text = f"""Materiał badawczy w postaci próbek dźwiękowych został przygotowany w formie plików MP3 (Moving Picture Experts Group Layer-3), próbkowanych z częstotliwością 44 kHz. 
Pliki audio zostały zapisane w trybie mono. Łącznie zebrano {len(mp3_files)} plików dzwiękowych.
    """
    report.add_raw(local_text)
    
    for mp3 in mp3_files:
        #print(mp3)
        #calculate_spectral_centroid(mp3)
        if ("backg" not in mp3 and "beep" not in mp3):
            data.append( analyze_audio_features(mp3, report=report) )
    return data
        


def process_meta_file(meta_file_path, output_dir):
    # Load meta.json file
    with open(meta_file_path, 'r') as f:
        meta_data = json.load(f)
    
    # Process each audio file in meta.json
    for entry in meta_data:
        fname = entry['fname']
        mp3_path = os.path.join(output_dir, f"{fname}.mp3")
        
        # Convert MP3 to WAV and calculate centroids
        if os.path.exists(mp3_path):
            wav_path = mp3_to_wav(mp3_path)
            frame_centroids, global_centroid = calculate_spectral_centroid(wav_path)
            
            # Add centroid data to the entry
            entry['global_centroid'] = global_centroid
            entry['frame_centroids'] = ','.join(map(str, frame_centroids))
            
            # Remove temporary WAV file after processing
            os.remove(wav_path)
        else:
            print(f"File {mp3_path} not found.")
    
    # Save updated meta.json with centroid data
    with open(meta_file_path, 'w') as f:
        json.dump(meta_data, f, indent=4)

def draw_2(df):
    global original
    # 1. List of numeric columns to analyze
    # (mfcc is omitted as it typically contains vectors/lists)
    # 2. Alternatively, split the 13 parameters into 13 separate columns
# This is better for Machine Learning
    mfcc_df = pd.DataFrame(df['mfcc'].tolist(), index=df.index)
    mfcc_df.columns = [f'mfcc_{i}' for i in range(1, 14)]
    df = pd.concat([df.drop('mfcc', axis=1), mfcc_df], axis=1)
    numeric_cols = ['centroid', 'f0', 'par']
    # The fixed line:
    df['bar_color'] = df['name'].apply(lambda x: "palegreen" if x in original else "skyblue")
    
    for x in range(1,14): numeric_cols.append(f"mfcc_{x}")
    
    #print(df.sort_values(by='mfcc_1', ascending=True).head(3).loc[:, ["name", "centroid"]])
    # 2. Obliczenie mediany dla całego zbioru (kolumna centroid)
    for x in numeric_cols:
        item_median = df[x].median()
        item_mean = df[x].mean()
        df = df.sort_values(by = x)

        # 3. Tworzenie wykresu
        plt.figure(figsize=(10, 7))
        bars = plt.bar(df['name'], df[x], color=df['bar_color'], alpha=0.8, label=x,
                       edgecolor='black', linewidth=0.8)
        for bar, color in zip(bars, df['bar_color']):
            if color == 'palegreen':
                bar.set_hatch('///')

        # Dodanie linii mediany
        plt.axhline(item_median, color='red', linestyle='--', linewidth=2, 
                    label=f'Median: {item_median:.2f}')
        plt.axhline(item_mean, color='green', linestyle='--', linewidth=2, 
                    label=f'Mean: {item_mean:.2f}')

        # Konfiguracja wykresu
        plt.title(None)
        plt.xticks(rotation='vertical')
        plt.ylabel('Value')
        plt.xlabel('Name')
        plt.legend()
        plt.tight_layout()
        plt.grid(axis='y', linestyle=':', alpha=0.7)

        plt.savefig(f"images/chart-{x}.jpeg")
        plt.close()

    # Wyświetlenie tabeli wynikowej
    

    # 2. Calculate statistics: min, max, avg, mediana, and std dev
    df_norm = df.copy()
    for col in numeric_cols:
        df_norm[col] = (df[col] - df[col].min()) / (df[col].max() - df[col].min())
    
    stats = df[numeric_cols].agg(['min', 'max', 'mean', 'median', 'std']).T
    stats.columns = ['min', 'max', 'avg', 'median', 'std dev']    
    #
    
    print("Calculated Statistics:")
    
    #temp_numeric_cols = stats.select_dtypes(include='number').columns
    #stats[temp_numeric_cols] = stats[temp_numeric_cols].astype(float).round(3)    
    stats = stats.round(3).applymap(lambda x: f"{x:.3f}")
    stats = stats.reset_index()
    stats.columns.values[0] = 'name'    
    #print(stats.to_latex(caption="Obliczone statystyki", label="tab:stats", position="ht"))        
    #print(stats)
    

    
    #temp_numeric_cols = stats.select_dtypes(include='number').columns
    stats_norm = df_norm[numeric_cols].agg(['mean', 'median', 'std']).T    
    
    stats_norm.columns = [ 'avg (norm)', 'median (norm)', 'std dev (norm)']        
    #stats_norm[temp_numeric_cols] = stats_norm[temp_numeric_cols].astype(float).round(3)    
    stats_norm = stats_norm.round(3).applymap(lambda x: f"{x:.3f}")
    stats_norm = stats_norm.reset_index()
    stats_norm.columns.values[0] = 'name'    
    #print(stats_norm)
    df_merged = pd.merge(stats, stats_norm, on="name")
    #df_merged = df_merged.drop(df_merged.columns[0], axis=1)
    print(df_merged.to_latex(caption="Obliczone statystyki", label="tab:stats", position="ht", index= False).replace("_","\\_"))
    #name & min & max & avg & median & std dev & avg (norm) & median (norm) & std dev (norm)
    
    mfc_std_dev_radar(stats_norm)
    
    
    #print("Calculated Statistics (normalized):")
    #print(pd.merge(stats, stats_norm, on="name"))
    
    #fizyczne = stats.loc[['centroid']]
    # print(fizyczne.nlargest(3, 'avg'))
    # print(fizyczne.nsmallest(3, 'avg'))

    # # 3. Draw the Chart with Standard Deviation (Error Bars)
    # plt.figure(figsize=(8, 6))
    # sns.scatterplot(data=df_norm, x='f0', y='centroid', hue='par', size='par')
    # plt.title('Relacja: Wysokość dźwięku (F0) vs Jasność (Centroid)')
    # plt.show()
    
    # Wybór kluczowych kolumn do analizy
    selected_cols = [ 'centroid', 'f0', 'par','mfcc_1', 'mfcc_2', 'mfcc_9']
    corr_matrix = df_norm[selected_cols].corr()

    # Rysowanie mapy ciepła (Heatmap)
    plt.figure(figsize=(8, 6))
    sns.heatmap(corr_matrix, annot=True, cmap='RdBu_r', center=0, fmt=".2f")
    plt.title('Korelacja między PAR, Centroid, MFCC_1 a F0')
    plt.savefig("images/correl-matrix.jpeg")
    plt.close()

    print("Macierz korelacji:")
    print(corr_matrix)
    

def mfc_std_dev_radar(stats):
    # 1. Filtrowanie danych
    mask = stats['name'].str.contains('mfcc')
    
    # Wyciągamy wartości i etykiety
    filtered_values = stats.loc[mask, 'std dev (norm)'].astype(float).tolist()
    labels = stats.loc[mask, 'name'].tolist()
    
    # 2. Zamknięcie pętli dla wykresu radarowego
    # Musimy dodać pierwszy element na koniec list, aby linia wróciła do początku
    values = filtered_values + [filtered_values[0]]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]

    # 3. Plotting
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    # Wypełnienie i linia
    ax.fill(angles, values, color='skyblue', alpha=0.25)
    ax.plot(angles, values, color='red', marker='o', linewidth=2)

    # Ustawienie etykiet na osiach (szprychach)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)

    # Tytuł i kosmetyka
    #plt.title("Standard Deviation of MFCC Features (Normalized)", size=15, pad=20)

    # Ustawienie limitu osi Y (od 0 do max + margines)
    ax.set_ylim(0, max(values) + 0.1) 

    # Zapis i wyświetlanie
    plt.tight_layout()
    plt.savefig("images/mfcc_std_dev_radar.jpeg", dpi=300)
    plt.show()
    plt.close(fig)


def compute_distance_stats(data):
    """
    Oblicza minimalne odległości euklidesowe w zbiorze oryginalnym MLT (n=10)
    oraz w zbiorze rozszerzonym (n=24). Drukuje wyniki gotowe do wklejenia do LaTeX.
    Dodatkowo liczy pary wg progów trudności percepcyjnej.
    """
    global original

    names = [d["name"] for d in data]

    # Budowa macierzy cech 16D
    feature_rows = []
    for d in data:
        row = np.concatenate((
            np.array([d["centroid"], d["f0"], d["par"]]),
            d["mfcc"]
        ))
        feature_rows.append(row)
    X = np.vstack(feature_rows)

    # Normalizacja Min-Max na całym zbiorze 24 próbek
    scaler = MinMaxScaler()
    X_norm = scaler.fit_transform(X)

    # Indeksy próbek oryginalnych MLT
    orig_indices = [i for i, n in enumerate(names) if n in original]
    orig_names   = [names[i] for i in orig_indices]

    # --- Macierz dla pełnego zbioru (24) ---
    D_full = pairwise_distances(X_norm, metric='euclidean')
    np.fill_diagonal(D_full, np.inf)  # ignoruj przekątną

    min_full = D_full.min()
    idx_full = np.unravel_index(D_full.argmin(), D_full.shape)
    pair_full = (names[idx_full[0]], names[idx_full[1]])

    # --- Macierz dla podzbioru oryginalnego (MLT) ---
    X_orig = X_norm[orig_indices]
    D_orig = pairwise_distances(X_orig, metric='euclidean')
    np.fill_diagonal(D_orig, np.inf)

    min_orig = D_orig.min()
    idx_orig = np.unravel_index(D_orig.argmin(), D_orig.shape)
    pair_orig = (orig_names[idx_orig[0]], orig_names[idx_orig[1]])

    # --- Liczby par wg progów trudności (tylko górny trójkąt) ---
    D_tri = pairwise_distances(X_norm, metric='euclidean')
    upper = D_tri[np.triu_indices(len(names), k=1)]
    N = int((upper < 0.80).sum())
    M = int(((upper >= 0.80) & (upper < 1.20)).sum())
    K = int((upper >= 1.20).sum())

    print("\n" + "="*60)
    print("WYNIKI DO WKLEJENIA DO LaTeX (sugestia B i C)")
    print("="*60)
    print(f"\n[Sugestia B] Zbiór oryginalny MLT (n={len(orig_indices)}):")
    print(f"  d_min = {min_orig:.3f}  |  para: {pair_orig[0]} -- {pair_orig[1]}")
    print(f"\n[Sugestia B] Zbiór rozszerzony (n={len(names)}):")
    print(f"  d_min = {min_full:.3f}  |  para: {pair_full[0]} -- {pair_full[1]}")
    print(f"\n[Sugestia C] Liczby par wg progów trudności:")
    print(f"  Trudny  (d < 0.80):            N = {N}")
    print(f"  Średni  (0.80 <= d < 1.20):    M = {M}")
    print(f"  Łatwy   (d >= 1.20):            K = {K}")
    print("="*60 + "\n")


# Define paths
meta_file_path = "meta.json"  # Path to meta.json
output_dir = "out"  # Directory containing MP3 files

# Process meta.json file and update with centroid data
#process_meta_file(meta_file_path, output_dir)

report = InfiReports()

#save_features("tmp.json", process_local(report))

data = load_features("tmp.json")
df = pd.DataFrame(data).round(3)
# 1. Round standard float columns (centroid, f0, par) to 3 decimal places
print(df.info())
draw_2(df)

l = '\\begin{tabular}{|c|c|c|c|}\hline' + "\n Name & F0 & PAR & Centroid \\\\ \multicolumn{4}{|c|}{Name} \\\\ \hline\n"
for d in data:
    
    s = ""
    for mfcc in d["mfcc"]:
        s += f"{mfcc:.3f} "
    l += f"""{d['name']} & {d['f0']:.3f} & {d['par']:.3f} & {d['centroid']:.3f} \\\\"""
    l+= "\multicolumn{4}{|c|}{"+s+"} \\\\ \hline\n"

l += """\end{tabular}"""

# print(l)
#df = pd.DataFrame(data)
#report.add_table(df)
html = "<table>"
html += f"""<tr><td>Nazwa</td><td>Centroid</td><td>F0</td><td>PAR</td></tr>
    <tr><td colspan='4'>MFCC</td></tr>
    """
for x in data:
    mfcc = ""
    for m in x['mfcc']:
        mfcc += "{:.3f}".format(m)+";"
    html += f"""<tr><td><b>{x['name']}</b></td><td>{x['centroid']:.3f}</td><td>{x['f0']:.3f}</td><td>{x['par']:.3f}</td>
    <tr><td colspan='4'><small>{mfcc}</small></td></tr>
    """
html += "</table>"
report.add_raw(html)
draw_chart(data, report)
compute_distance_stats(data)

report.save_html("report.html")



# rag_service/services/resolver.py
# DECIDIR DE QUÉ ARTÍCULO HABLAMOS. Esta es la parte delicada de todo el RAG.
#
# El problema: Wikipedia no se busca por spotify_track_id, se busca por texto.
# Una canción llamada "Normal" tiene un título tan genérico que el buscador
# devuelve el artículo de la distribución normal, el de "grupo normal" y veinte
# cosas más. Si nos quedamos con el primer resultado, el modelo respondería con
# total seguridad una barbaridad — y una alucinación segura de sí misma es el
# peor resultado posible aquí.
#
# La defensa es puntuar los candidatos y EXIGIR UN MÍNIMO. Si nada llega al
# mínimo, este módulo devuelve None y el servicio dice honestamente que no tiene
# información. Preferimos callar a inventar.
import re
import unicodedata

# Puntaje mínimo para aceptar un artículo como "es esta canción". Sale de la
# combinación de señales de abajo: en la práctica obliga a que el título case
# con la canción Y a que el artista aparezca por algún lado, o a que el título
# venga desambiguado explícitamente como canción.
MIN_SCORE = 4

# Palabras que Wikipedia usa entre paréntesis para desambiguar cosas musicales.
MUSIC_HINTS = ("cancion", "song", "album", "sencillo", "single")


def normalize(text: str) -> str:
    """
    Minúsculas, sin tildes y sin puntuación. Así "Bailá Conmigo" y
    "baila conmigo" se comparan como iguales.
    """
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_song_title(name: str) -> str:
    """
    Spotify adorna los títulos: "Normal - Remastered 2011",
    "Si Tú La Ves (feat. Alejandro Sanz)", "Perro Negro (Remix)". Ese ruido
    hunde la búsqueda, así que lo quitamos antes de preguntar.
    """
    name = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", name)   # (feat...) [Remix]
    name = re.sub(r"\s*-\s*.*$", "", name)                 # - Remastered 2011
    return name.strip() or name


def _first_artist(artist: str) -> str:
    """
    'Feid, Young Miko' -> 'Feid'. Para buscar basta el principal; meter a todos
    los featuring ensucia la consulta.
    """
    return re.split(r"[,;&]| feat| ft\.| x ", artist, flags=re.IGNORECASE)[0].strip()


def score_song_candidate(candidate: dict, song: str, artist: str) -> int:
    """
    Cuánto se parece este artículo a "la canción X de Y". Señales, de más a
    menos fiable:

      +3  el título del artículo ES el nombre de la canción (exacto, ignorando
          el paréntesis desambiguador). Es la señal más fuerte.
      +2  el título CONTIENE el nombre de la canción.
      +3  el título trae "(canción)" / "(song)" — Wikipedia nos está diciendo
          explícitamente que esto es música.
      +2  el artista aparece en el resumen del artículo. Esto es lo que separa
          la canción "Normal" de Feid de la distribución normal.
      -4  el resumen huele a que NO es música y el artista no aparece.
    """
    title = candidate["title"]
    snippet = candidate.get("snippet", "")

    n_title = normalize(title)
    n_song = normalize(song)
    n_artist = normalize(_first_artist(artist))
    n_snippet = normalize(snippet)

    # El título sin el paréntesis de desambiguación: "Normal (canción)" -> "normal"
    n_title_bare = normalize(re.sub(r"\s*\([^)]*\)\s*$", "", title))

    score = 0

    if n_title_bare == n_song:
        score += 3
    elif n_song and n_song in n_title:
        score += 2

    if any(hint in n_title for hint in MUSIC_HINTS):
        score += 3

    artist_present = bool(n_artist) and n_artist in n_snippet
    if artist_present:
        score += 2

    # Si ni el artista aparece ni el título está marcado como musical, lo más
    # probable es que sea un homónimo de otro tema. Lo penalizamos fuerte.
    if not artist_present and not any(hint in n_title for hint in MUSIC_HINTS):
        score -= 4

    return score


def pick_best(candidates: list[dict], song: str, artist: str) -> dict | None:
    """El mejor candidato, o None si ninguno llega a MIN_SCORE."""
    if not candidates:
        return None

    scored = [
        {**c, "score": score_song_candidate(c, song, artist)} for c in candidates
    ]
    best = max(scored, key=lambda c: c["score"])
    return best if best["score"] >= MIN_SCORE else None


def score_artist_candidate(candidate: dict, artist: str) -> int:
    """
    Plan B: si no hay artículo de la canción, sirve el del ARTISTA. Aquí el
    listón es distinto — el título tiene que ser el nombre del artista y el
    resumen tiene que oler a música.
    """
    n_title_bare = normalize(re.sub(r"\s*\([^)]*\)\s*$", "", candidate["title"]))
    n_artist = normalize(_first_artist(artist))
    n_snippet = normalize(candidate.get("snippet", ""))

    if n_title_bare != n_artist:
        return 0

    score = 3
    if any(
        word in n_snippet
        for word in ("cantante", "musico", "rapero", "banda", "singer", "rapper",
                     "musician", "band", "compositor", "songwriter")
    ):
        score += 2
    return score


def pick_best_artist(candidates: list[dict], artist: str) -> dict | None:
    if not candidates:
        return None
    scored = [{**c, "score": score_artist_candidate(c, artist)} for c in candidates]
    best = max(scored, key=lambda c: c["score"])
    return best if best["score"] >= MIN_SCORE else None

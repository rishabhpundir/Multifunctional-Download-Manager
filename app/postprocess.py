import os, shutil, requests
from guessit import guessit
from subliminal import download_best_subtitles, region, save_subtitles, Video
from babelfish import Language
from dotenv import load_dotenv

load_dotenv()

TMDB_KEY = os.getenv("TMDB_API_KEY")
MEDIA_ROOT = os.getenv("MEDIA_ROOT")


def _dest_paths(meta, kind, src_path):
    # match your folder names exactly
    movies_dir = os.path.join(MEDIA_ROOT, "movies")
    tv_dir = os.path.join(MEDIA_ROOT, "tvshows")

    if kind == "movie":
        title = meta.get("title") or "Unknown"
        year = meta.get("year")
        title_folder = f"{title} ({year})" if year else title
        folder = os.path.join(movies_dir, title_folder)
        os.makedirs(folder, exist_ok=True)
        return folder, os.path.join(folder, os.path.basename(src_path)), os.path.join(folder, "poster.jpg")
    else:
        show = meta.get("title") or "Unknown Show"
        season = f"Season {int(meta.get('season', 1)):02d}"
        folder = os.path.join(tv_dir, show, season)
        os.makedirs(folder, exist_ok=True)
        # show-level poster (one level up from season)
        return folder, os.path.join(folder, os.path.basename(src_path)), os.path.join(os.path.dirname(folder), "poster.jpg")


def _tmdb_poster(meta, poster_path):
    title, year = meta.get("title"), meta.get("year")
    if not title or not TMDB_KEY:
        return
    url = "https://api.themoviedb.org/3/search/multi"
    try:
        r = requests.get(url, params={"api_key": TMDB_KEY, "query": title, "year": year}, timeout=20)
        j = r.json()
        if not j.get("results"):
            return
        poster = j["results"][0].get("poster_path")
        if not poster:
            return
        img = requests.get(f"https://image.tmdb.org/t/p/w780{poster}", timeout=20).content
        with open(poster_path, "wb") as f:
            f.write(img)
    except Exception:
        pass


def _download_subs(video_path):
    region.configure("dogpile.cache.memory")
    vid = Video.fromname(video_path)
    subs = download_best_subtitles({vid}, {Language("eng")})
    if subs.get(vid):
        save_subtitles(vid, subs[vid])


def basic_meta_from_name(path):
    g = guessit(os.path.basename(path))
    meta = {"title": g.get("title"), "year": g.get("year")}
    if "season" in g:
        meta["season"] = g["season"]
    if "episode" in g:
        meta["episode"] = g["episode"]
    return meta


def move_and_enrich(src_path, kind):
    meta = basic_meta_from_name(src_path)
    folder, dest_video, poster_path = _dest_paths(meta, kind, src_path)
    if os.path.abspath(src_path) != os.path.abspath(dest_video):
        shutil.move(src_path, dest_video)
    _tmdb_poster(meta, poster_path)
    _download_subs(dest_video)
    return folder



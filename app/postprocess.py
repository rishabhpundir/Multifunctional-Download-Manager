import os, shutil, requests
from guessit import guessit
from subliminal import download_best_subtitles, region, save_subtitles, Video
from babelfish import Language
from dogpile.cache import exception as dp_exc
from dotenv import load_dotenv

load_dotenv()

TMDB_API_TOKEN = os.getenv("TMDB_API_TOKEN")
MEDIA_ROOT = os.getenv("MEDIA_ROOT")
USE_TMDB = (os.getenv("TMDB_ENABLED", "1").lower() not in ("0","false","no"))


def _dest_paths(meta, kind, src_path):
    # match your folder names exactly
    movies_dir = os.path.join(MEDIA_ROOT, "movies")
    tv_dir = os.path.join(MEDIA_ROOT, "tvshows")

    if kind == "movies":
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
    if not USE_TMDB:
        return
    title, year = meta.get("title"), meta.get("year")
    if not title or not TMDB_API_TOKEN:
        return

    url = "https://api.themoviedb.org/3/search/multi"

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {TMDB_API_TOKEN}"
    }
    
    params = {"query": title, "include_adult": "true"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        j = r.json()
        if not j.get("results"):
            return
        poster = j["results"][0].get("poster_path")
        if not poster:
            return
        img = requests.get(f"https://image.tmdb.org/t/p/w780{poster}", timeout=20).content
        with open(poster_path, "wb") as f:
            f.write(img)
    except Exception as e:
        print(f"Error while getting poster : \n{e}")


def _download_subs(video_path):
    try:
        region.configure("dogpile.cache.memory")
    except dp_exc.RegionAlreadyConfigured:
        pass

    try:
        # Provider config: only set opensubtitles if creds present
        provider_configs = {}
        osu = os.getenv("OPENSUBTITLES_USER")
        osp = os.getenv("OPENSUBTITLES_PASS")
        if osu and osp:
            provider_configs["opensubtitles"] = {"username": osu, "password": osp}

        vid = Video.fromname(video_path)

        subs = download_best_subtitles(
            {vid},
            {Language("eng")},
            providers=None,               # use default provider list
            provider_configs=provider_configs
        )
        if subs.get(vid):
            save_subtitles(vid, subs[vid])
    except Exception as e:
        print(f"Error while downloading subtitles: \n{e}")


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
    folder  = folder.rsplit("/", 1)[0] if "tvshows" in folder else folder
    if os.path.abspath(src_path) != os.path.abspath(dest_video):
        shutil.move(src_path, dest_video)
    # _tmdb_poster(meta, poster_path)
    _download_subs(dest_video)
    return folder



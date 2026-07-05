from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
from PIL import Image
import numpy as np
from groq import Groq
import requests
import re, json, os, time, base64
from datetime import datetime
from ddgs import DDGS

try:
    import local_secrets
except ImportError:
    local_secrets = None

app = Flask(__name__)
def _load_local_secret(name: str) -> str:
    if local_secrets is None:
        return ""
    return str(getattr(local_secrets, name, "")).strip()


def _get_secret(name: str, local_value: str = "", default: str = "") -> str:
    return os.environ.get(name, "").strip() or local_value or default


app.secret_key = _get_secret("FLASK_SECRET_KEY", _load_local_secret("FLASK_SECRET_KEY"), "styleai-dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///styleai.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "static"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

GROQ_API_KEY = _get_secret("GROQ_API_KEY", _load_local_secret("GROQ_API_KEY"))
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def _groq_completion(**kwargs):
    if not groq_client:
        return None
    try:
        return groq_client.chat.completions.create(**kwargs)
    except Exception as exc:
        print(f"[Groq] Request failed: {exc}")
        return None

# ── Paste your Gemini API key here ────────────────────────
GEMINI_API_KEY = _get_secret("GEMINI_API_KEY", _load_local_secret("GEMINI_API_KEY"))
GEMINI_VISION_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent?key=" + GEMINI_API_KEY
)

# ─── Models ───────────────────────────────────────────────
class User(UserMixin, db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80), unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    analyses   = db.relationship("Analysis", backref="user", lazy=True)

class Analysis(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    gender       = db.Column(db.String(20))
    occasion     = db.Column(db.String(50))
    skin_tone    = db.Column(db.String(30))   # now holds full label e.g. "Wheatish-warm"
    image_path   = db.Column(db.String(200))
    ai_output    = db.Column(db.Text)
    items_json   = db.Column(db.Text)
    is_favourite = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

class WardrobeItem(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name       = db.Column(db.String(100), nullable=False)
    category   = db.Column(db.String(30))
    color      = db.Column(db.String(40))
    image_path = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_image_url():
    def image_url(path):
        if not path:
            return url_for("static", filename="")
        normalized = str(path).replace("\\", "/").lstrip("/")
        if normalized.startswith("static/"):
            normalized = normalized[len("static/"):]
        else:
            normalized = os.path.basename(normalized)
        return url_for("static", filename=normalized)

    return {"image_url": image_url}

# ─── Skin Tone Engine ─────────────────────────────────────
#
# 6 Indian skin tones with warm/cool undertone distinction:
#   Fair | Wheatish-warm | Wheatish-cool | Dusky | Deep-warm | Deep-cool
#
# Strategy:
#   1. Try Gemini 1.5 Flash Vision (primary — most accurate)
#   2. Fall back to improved pixel analysis (never crashes the app)

# Valid tone labels — used to validate Gemini's response
VALID_TONES = {
    "fair", "wheatish-warm", "wheatish-cool",
    "dusky", "deep-warm", "deep-cool"
}

def _encode_image_base64(filepath: str) -> tuple[str, str]:
    """Return (base64_data, mime_type) for a JPEG/PNG image."""
    ext = os.path.splitext(filepath)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    with open(filepath, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return data, mime


def _gemini_detect_skin_tone(filepath: str) -> str | None:
    """
    Send the photo to Gemini 1.5 Flash and ask for one of the 6 Indian
    skin tone labels.  Returns the label string or None on any error.
    """
    try:
        img_data, mime_type = _encode_image_base64(filepath)

        prompt_text = """You are an expert in Indian skin tone analysis.
Look at the person's face and exposed skin in this photo.
Classify their skin tone into EXACTLY ONE of these 6 Indian skin tone categories:

1. Fair           — very light skin, cool/neutral undertone
2. Wheatish-warm  — light-medium skin, golden/yellow undertone (most common North Indian)
3. Wheatish-cool  — light-medium skin, pink/rosy undertone
4. Dusky          — medium-brown skin, neutral or olive undertone
5. Deep-warm      — dark brown skin, warm/golden/reddish undertone
6. Deep-cool      — dark brown skin, cool/bluish-neutral undertone

Rules:
- Respond with ONLY the label (e.g. "Wheatish-warm"). No extra words.
- If the image has no visible person or skin, respond with "Fair".
- Consider lighting but try to assess the natural skin tone."""

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt_text},
                    {"inline_data": {"mime_type": mime_type, "data": img_data}}
                ]
            }]
        }

        resp = requests.post(
            GEMINI_VISION_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        resp.raise_for_status()
        result = resp.json()

        # Extract text from Gemini response
        tone_raw = (
            result["candidates"][0]["content"]["parts"][0]["text"]
            .strip()
            .strip('"\'')
        )

        # Validate — must be one of our 6 labels (case-insensitive)
        tone_normalized = tone_raw.lower().replace(" ", "-")
        if tone_normalized in VALID_TONES:
            # Return in Title-Case-with-hyphen format
            return tone_raw.title() if "-" not in tone_raw else "-".join(
                p.capitalize() for p in tone_raw.split("-")
            )

        # Gemini gave something unexpected — try a fuzzy match
        for valid in VALID_TONES:
            if valid in tone_normalized or tone_normalized in valid:
                return "-".join(p.capitalize() for p in valid.split("-"))

        print(f"[Gemini] Unexpected tone label: '{tone_raw}' — falling back")
        return None

    except Exception as e:
        print(f"[Gemini] Skin tone detection failed: {e}")
        return None


def _pixel_detect_skin_tone(filepath: str) -> str:
    """
    Improved pixel-based fallback using RGB channel ratios for
    warm/cool undertone detection in addition to brightness.

    Returns one of the 6 Indian skin tone labels.
    """
    img = Image.open(filepath).convert("RGB")
    arr = np.array(img.resize((100, 100)), dtype=float)

    # Sample the centre quarter of the image (face-biased)
    h, w = arr.shape[:2]
    center = arr[h // 4: 3 * h // 4, w // 4: 3 * w // 4]

    avg_r = np.mean(center[:, :, 0])
    avg_g = np.mean(center[:, :, 1])
    avg_b = np.mean(center[:, :, 2])
    brightness = (avg_r + avg_g + avg_b) / 3

    # Warm undertone: R >> B  |  Cool undertone: B relatively higher
    warm = (avg_r - avg_b) > 15

    if brightness > 210:
        return "Fair"
    elif brightness > 170:
        return "Wheatish-warm" if warm else "Wheatish-cool"
    elif brightness > 120:
        return "Dusky"
    else:
        return "Deep-warm" if warm else "Deep-cool"


def detect_skin_tone(filepath: str) -> str:
    """
    Primary entry point for skin tone detection.
    Tries Gemini Vision first; falls back to pixel analysis.
    """
    # Skip Gemini if no real API key is set
    if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
        tone = _gemini_detect_skin_tone(filepath)
        if tone:
            print(f"[Gemini] Detected skin tone: {tone}")
            return tone
        print("[Gemini] Using pixel fallback")
    else:
        print("[Skin Tone] No Gemini key set — using pixel fallback")

    tone = _pixel_detect_skin_tone(filepath)
    print(f"[Pixel] Detected skin tone: {tone}")
    return tone


# ─── Curated Outfit Library ───────────────────────────────
# Every outfit is hand-designed for coherence.
# Structure: (item_name, search_query)
# Items are always: [main garment, bottom/layer, footwear, jewellery 1, jewellery 2, bag/accessory]
# The LLM is only used to PICK WHICH SET to show (by index), never to invent items.

OUTFIT_LIBRARY = {
    "female": {
        "casual": [
            [   # Set A — kurti + straight pants (everyday)
                ("Printed Kurti",        "women printed cotton kurti white background"),
                ("Straight Pants",       "women straight fit pants ethnic white background"),
                ("Kolhapuri Flats",      "women kolhapuri flat sandals white background"),
                ("Stud Earrings",        "women small gold stud earrings white background"),
                ("Thin Gold Bangles",    "women thin gold bangles set white background"),
                ("Jute Tote Bag",        "women jute tote bag ethnic white background"),
            ],
            [   # Set B — co-ord set (trendy casual)
                ("Ethnic Co-ord Set",    "women ethnic co-ord set kurta palazzo white background"),
                ("Dupatta",              "women light dupatta stole white background"),
                ("Block Heeled Sandals", "women block heel sandals ethnic white background"),
                ("Oxidised Earrings",    "women oxidised silver earrings white background"),
                ("Beaded Bracelet",      "women beaded bracelet ethnic white background"),
                ("Sling Bag",            "women fabric sling bag ethnic white background"),
            ],
            [   # Set C — kurti + leggings (comfortable casual)
                ("A-line Kurti",         "women a-line kurti floral print white background"),
                ("Churidar Leggings",    "women churidar leggings black white background"),
                ("Juttis",               "women jutti flat shoes ethnic white background"),
                ("Hoop Earrings",        "women small gold hoop earrings white background"),
                ("Stack Rings",          "women gold stack rings white background"),
                ("Canvas Potli",         "women small canvas potli bag white background"),
            ],
        ],
        "party": [
            [   # Set A — sharara (festive party)
                ("Sharara Set",          "women sharara set embroidered party white background"),
                ("Embroidered Dupatta",  "women heavy embroidered dupatta white background"),
                ("Heeled Sandals",       "women heeled ethnic sandals gold white background"),
                ("Jhumkas",              "women gold jhumka earrings white background"),
                ("Stone Bangle Set",     "women stone studded bangle set white background"),
                ("Potli Bag",            "women embroidered potli bag party white background"),
            ],
            [   # Set B — anarkali (elegant party)
                ("Floor-length Anarkali","women floor length anarkali suit party white background"),
                ("Churidar",             "women churidar pants white background"),
                ("Wedge Heels",          "women wedge heels ethnic white background"),
                ("Chandbali Earrings",   "women chandbali earrings gold white background"),
                ("Pearl Necklace",       "women pearl necklace white background"),
                ("Clutch Bag",           "women embroidered clutch bag white background"),
            ],
        ],
        "formal": [
            [   # Set A — silk saree (classic formal)
                ("Silk Saree",           "women silk saree drape formal white background"),
                ("Saree Blouse",         "women saree blouse embroidered white background"),
                ("Heeled Sandals",       "women block heel sandals formal gold white background"),
                ("Gold Necklace Set",    "women gold necklace set formal white background"),
                ("Jhumkas",              "women gold jhumka earrings white background"),
                ("Silk Clutch",          "women silk clutch bag formal white background"),
            ],
            [   # Set B — lehenga (grand formal)
                ("Velvet Lehenga",       "women velvet lehenga formal white background"),
                ("Embroidered Blouse",   "women lehenga blouse heavy embroidery white background"),
                ("Heels",                "women stiletto heels ethnic gold white background"),
                ("Maang Tikka",          "women maang tikka gold formal white background"),
                ("Jhumkas",              "women gold jhumka earrings white background"),
                ("Potli Bag",            "women bridal potli bag embroidered white background"),
            ],
        ],
        "business": [
            [   # Set A — salwar kameez (office-ready)
                ("Formal Salwar Kameez", "women formal salwar kameez office white background"),
                ("Straight Dupatta",     "women plain straight dupatta formal white background"),
                ("Block Heels",          "women block heels formal white background"),
                ("Stud Earrings",        "women pearl stud earrings white background"),
                ("Thin Watch",           "women slim watch rose gold white background"),
                ("Structured Handbag",   "women structured handbag office white background"),
            ],
        ],
        "wedding": [
            [
                ("Bridal Lehenga",       "women bridal lehenga red gold white background"),
                ("Heavy Blouse",         "women bridal lehenga blouse heavy embroidery white background"),
                ("Heels",                "women bridal heels gold white background"),
                ("Maang Tikka",          "women bridal maang tikka gold white background"),
                ("Jhumkas",              "women bridal jhumka gold white background"),
                ("Bridal Potli",         "women bridal potli bag red gold white background"),
            ],
        ],
        "sangeet": [
            [
                ("Sharara Set",          "women sharara set sangeet pink white background"),
                ("Embroidered Dupatta",  "women heavy dupatta sangeet white background"),
                ("Block Heels",          "women block heels gold ethnic white background"),
                ("Chandbali Earrings",   "women chandbali earrings sangeet white background"),
                ("Choker Necklace",      "women kundan choker necklace white background"),
                ("Potli Bag",            "women potli bag sangeet ethnic white background"),
            ],
        ],
        "mehndi": [
            [
                ("Green Anarkali",       "women green anarkali suit mehndi white background"),
                ("Churidar",             "women churidar leggings white background"),
                ("Juttis",               "women jutti green gold white background"),
                ("Jhumkas",              "women green gold jhumka earrings white background"),
                ("Glass Bangles",        "women green glass bangles set white background"),
                ("Potli Bag",            "women potli bag green mehndi white background"),
            ],
        ],
        "haldi": [
            [
                ("Yellow Sharara",       "women yellow sharara set haldi white background"),
                ("Yellow Dupatta",       "women yellow dupatta stole white background"),
                ("Flats",                "women yellow flat sandals ethnic white background"),
                ("Floral Jhumkas",       "women floral jhumka earrings haldi white background"),
                ("Floral Bangles",       "women floral bangles set haldi white background"),
                ("Potli Bag",            "women yellow potli bag haldi white background"),
            ],
        ],
        "puja": [
            [
                ("Cotton Saree",         "women cotton saree simple puja white background"),
                ("Saree Blouse",         "women simple saree blouse white background"),
                ("Flats",                "women flat sandals ethnic white background"),
                ("Gold Studs",           "women gold stud earrings simple white background"),
                ("Thin Bangles",         "women thin gold bangles white background"),
                ("Potli",                "women small potli bag cotton white background"),
            ],
        ],
        "festival": [
            [
                ("Silk Kurti",           "women silk kurti festival white background"),
                ("Silk Palazzo",         "women silk palazzo pants white background"),
                ("Kolhapuri Heels",      "women kolhapuri heels festival white background"),
                ("Jhumkas",              "women gold jhumka earrings festival white background"),
                ("Kundan Necklace",      "women kundan necklace festival white background"),
                ("Embroidered Potli",    "women embroidered potli bag festival white background"),
            ],
        ],
    },
    "male": {
        "casual": [
            [
                ("Linen Kurta",          "men linen kurta casual white background"),
                ("Churidar",             "men churidar pants white background"),
                ("Kolhapuri Chappals",   "men kolhapuri chappal white background"),
                ("Bracelet",             "men leather bracelet white background"),
                ("Casual Watch",         "men casual watch white background"),
                ("Messenger Bag",        "men canvas messenger bag white background"),
            ],
        ],
        "party": [
            [
                ("Indo-Western Kurta",   "men indo western kurta party white background"),
                ("Slim Trousers",        "men slim fit trousers ethnic white background"),
                ("Loafers",              "men ethnic loafers white background"),
                ("Metal Bracelet",       "men metal bracelet white background"),
                ("Watch",                "men dress watch white background"),
                ("Clutch",               "men ethnic clutch white background"),
            ],
        ],
        "formal": [
            [
                ("Sherwani",             "men sherwani formal white background"),
                ("Churidar",             "men churidar formal white background"),
                ("Mojari Shoes",         "men mojari shoes ethnic white background"),
                ("Pocket Square",        "men silk pocket square white background"),
                ("Brooch",               "men sherwani brooch pin white background"),
                ("Watch",                "men classic dress watch white background"),
            ],
        ],
        "business": [
            [
                ("Nehru Jacket",         "men nehru jacket formal white background"),
                ("Formal Shirt",         "men formal shirt white background"),
                ("Formal Trousers",      "men formal trousers white background"),
                ("Oxford Shoes",         "men oxford shoes white background"),
                ("Watch",                "men formal watch white background"),
                ("Briefcase",            "men leather briefcase white background"),
            ],
        ],
        "wedding": [
            [
                ("Sherwani",             "men bridal sherwani wedding white background"),
                ("Churidar",             "men churidar wedding white background"),
                ("Mojari Shoes",         "men wedding mojari white background"),
                ("Safa/Turban",          "men wedding safa turban white background"),
                ("Brooch",               "men sherwani brooch wedding white background"),
                ("Watch",                "men gold dress watch white background"),
            ],
        ],
        "sangeet": [
            [
                ("Silk Kurta",           "men silk kurta sangeet white background"),
                ("Dhoti Pants",          "men dhoti pants white background"),
                ("Mojari",               "men mojari sangeet white background"),
                ("Watch",                "men watch sangeet white background"),
                ("Bracelet",             "men metal bracelet white background"),
                ("Pocket Square",        "men pocket square white background"),
            ],
        ],
        "mehndi": [
            [
                ("Printed Kurta",        "men printed kurta mehndi white background"),
                ("Churidar",             "men churidar white background"),
                ("Juttis",               "men jutti shoes mehndi white background"),
                ("Watch",                "men casual watch white background"),
                ("Bracelet",             "men bracelet white background"),
                ("Sling Bag",            "men sling bag ethnic white background"),
            ],
        ],
        "haldi": [
            [
                ("Yellow Kurta",         "men yellow kurta haldi white background"),
                ("White Pyjama",         "men white pyjama kurta white background"),
                ("Flats",                "men flat sandals white background"),
                ("Watch",                "men casual watch white background"),
                ("Bracelet",             "men thread bracelet white background"),
                ("Pocket Square",        "men yellow pocket square white background"),
            ],
        ],
        "puja": [
            [
                ("Simple Kurta Pyjama",  "men kurta pyjama simple puja white background"),
                ("Kolhapuri Chappals",   "men kolhapuri chappal white background"),
                ("Watch",                "men simple watch white background"),
                ("Bracelet",             "men rudraksha bracelet white background"),
                ("Pocket Square",        "men simple pocket square white background"),
                ("Potli",                "men potli bag puja white background"),
            ],
        ],
        "festival": [
            [
                ("Silk Kurta",           "men silk kurta festival white background"),
                ("Straight Pants",       "men straight pants ethnic white background"),
                ("Mojari",               "men mojari festival white background"),
                ("Watch",                "men gold watch white background"),
                ("Bracelet",             "men gold bracelet white background"),
                ("Pocket Square",        "men silk pocket square festival white background"),
            ],
        ],
    },
}

import random

def get_clothing_items(gender, occasion, skin_tone):
    """
    Returns a guaranteed-coherent outfit set from the curated library.
    LLM is used ONLY to pick the best set variant for the skin tone —
    it never invents items, so coherence is always preserved.
    """
    is_female = gender.lower() == "female"
    gender_key = "female" if is_female else "male"
    occ_key = occasion.lower()

    # Find the outfit sets for this gender + occasion
    gender_lib = OUTFIT_LIBRARY.get(gender_key, OUTFIT_LIBRARY["female"])
    sets = gender_lib.get(occ_key, gender_lib.get("casual"))

    # If only one set, return it directly — no LLM needed
    if len(sets) == 1:
        return [{"item": name, "search": search} for name, search in sets[0]]

    # Multiple sets: ask the LLM to pick the best one for this skin tone
    # (LLM picks an index, never invents items — coherence guaranteed)
    sets_desc = "\n".join(
        f"Set {i+1}: {', '.join(name for name, _ in s)}"
        for i, s in enumerate(sets)
    )
    pick_prompt = f"""You are an Indian fashion expert.
A {gender} with {skin_tone} skin tone needs an outfit for: {occasion}.

Choose the BEST set from below based on which colours and styles complement {skin_tone} skin tone most.
{sets_desc}

Reply with ONLY the set number (e.g. "1" or "2"). Nothing else."""

    chosen_index = 0  # default to Set 1
    try:
        resp = _groq_completion(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": pick_prompt}],
            max_tokens=5
        )
        if resp and getattr(resp, "choices", None):
            raw = resp.choices[0].message.content.strip()
            num = int(re.search(r'\d', raw).group())
            chosen_index = max(0, min(num - 1, len(sets) - 1))
    except:
        chosen_index = 0

    chosen_set = sets[chosen_index]
    item_names = [name for name, _ in chosen_set]
    return _generate_search_queries(item_names, gender, occasion, skin_tone)


# Skin-tone colour palette for search query variation
SKIN_TONE_COLOURS = {
    "Fair":          ["pastel pink", "ivory", "powder blue", "mint green", "blush"],
    "Wheatish-warm": ["mustard yellow", "terracotta", "peach", "warm orange", "golden beige"],
    "Wheatish-cool": ["lavender", "dusty rose", "sage green", "mauve", "lilac"],
    "Dusky":         ["emerald green", "deep teal", "magenta", "royal blue", "cobalt"],
    "Deep-warm":     ["rich maroon", "burnt orange", "copper gold", "deep red", "bronze"],
    "Deep-cool":     ["electric blue", "fuchsia pink", "bright yellow", "deep purple", "white gold"],
}


def _generate_search_queries(item_names, gender, occasion, skin_tone):
    """
    Build short, DDG-friendly search queries per item.
    Keeps queries under 8 words — DDG fails on long/complex queries.
    Adds a random colour from the skin-tone palette for variety.
    """
    shade_options = SKIN_TONE_COLOURS.get(skin_tone, SKIN_TONE_COLOURS["Dusky"])
    shade = random.choice(shade_options)
    g = "women" if gender.lower() == "female" else "men"

    results = []
    for name in item_names:
        name_lower = name.lower()

        # Match item type → concise query (max ~6 words, no long phrases)
        if any(k in name_lower for k in ["saree", "sari"]):
            q = f"{g} {shade} saree indian ethnic"
        elif "blouse" in name_lower:
            q = f"{g} saree blouse {shade}"
        elif "lehenga" in name_lower:
            q = f"{g} lehenga {shade} ethnic"
        elif any(k in name_lower for k in ["kurta", "kurti", "kameez", "salwar"]):
            q = f"{g} {shade} kurta ethnic wear"
        elif "anarkali" in name_lower:
            q = f"{g} anarkali {shade} ethnic"
        elif "sharara" in name_lower:
            q = f"{g} sharara {shade} ethnic"
        elif "dupatta" in name_lower:
            q = f"dupatta {shade} ethnic stole"
        elif any(k in name_lower for k in ["heels", "sandals", "wedge"]):
            q = f"{g} {shade} heels sandals ethnic"
        elif any(k in name_lower for k in ["jutti", "juttis", "mojari"]):
            q = f"{g} jutti ethnic footwear"
        elif "flats" in name_lower:
            q = f"{g} flat sandals ethnic"
        elif "chappal" in name_lower:
            q = f"{g} kolhapuri chappal ethnic"
        elif "watch" in name_lower:
            q = f"{g} wristwatch fashion product"
        elif any(k in name_lower for k in ["handbag", "bag", "clutch", "potli", "tote", "sling"]):
            q = f"{g} {name_lower} ethnic fashion"
        elif any(k in name_lower for k in ["jhumka", "jhumkas", "chandbali"]):
            q = f"jhumka earrings gold ethnic"
        elif any(k in name_lower for k in ["stud", "studs"]):
            q = "gold stud earrings simple jewellery"
        elif any(k in name_lower for k in ["jhumka", "jhumkas", "chandbali"]):
            q = "gold jhumka earrings ethnic jewellery"
        elif any(k in name_lower for k in ["earring", "hoop"]):
            q = "gold earrings ethnic jewellery"
        elif any(k in name_lower for k in ["choker", "kundan"]):
            q = "kundan choker necklace ethnic jewellery"
        elif "necklace" in name_lower:
            q = "gold necklace ethnic jewellery set"
        elif any(k in name_lower for k in ["bangles", "bangle"]):
            q = "gold bangles set ethnic jewellery"
        elif "bracelet" in name_lower:
            q = "gold bracelet ethnic jewellery"
        elif "tikka" in name_lower:
            q = f"maang tikka gold bridal"
        elif "brooch" in name_lower:
            q = f"brooch pin fashion product"
        elif "sherwani" in name_lower:
            q = f"men sherwani {shade} ethnic"
        elif "churidar" in name_lower:
            q = f"churidar pants ethnic fashion"
        elif "nehru" in name_lower:
            q = f"men nehru jacket ethnic"
        elif any(k in name_lower for k in ["straight pant", "palazzo"]):
            q = f"{g} {name_lower} only ethnic"
        elif any(k in name_lower for k in ["trouser", "pants", "pyjama", "churidar", "legging"]):
            q = f"{g} {name_lower} only ethnic bottom"
        elif "jacket" in name_lower:
            q = f"{g} ethnic jacket {shade}"
        else:
            # Generic short fallback
            q = f"{g} {name_lower} {shade} ethnic fashion"

        results.append({"item": name, "search": q})

    return results


def _scrape_image_urls(query):
    urls = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=20))
        random.shuffle(results)
        for r in results:
            u = r.get('image', '')
            if u and int(r.get('width', 0)) >= 150 and int(r.get('height', 0)) >= 150:
                urls.append(u)
        if urls:
            return urls
    except Exception as e:
        print(f'  [DDG] failed: {e}')
    try:
        q = requests.utils.quote(query)
        resp = requests.get(f'https://www.google.com/search?q={q}&tbm=isch&num=20',
                            headers=headers, timeout=10)
        if resp.status_code == 200:
            found = re.findall(r'"(https://[^"]+\.(?:jpg|jpeg|png|webp))"', resp.text)
            found = [u for u in found if 'gstatic' not in u]
            random.shuffle(found)
            urls = found[:20]
    except Exception as e:
        print(f'  [Google] failed: {e}')
    return urls


def fetch_item_image(item_name, search_query, filename):
    BLOCKED = ['myntra.com', 'ajio.com', 'flipkart.com', 'amazon.in', 'nykaa.com', 'meesho.com', 'gstatic.com']
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'}
    try:
        image_urls = _scrape_image_urls(search_query)
        for url in image_urls:
            if any(d in url for d in BLOCKED):
                continue
            try:
                resp = requests.get(url, timeout=8, headers=headers)
                ct = resp.headers.get('content-type', '')
                if resp.status_code == 200 and 'image' in ct and 'svg' not in ct and len(resp.content) > 3000:
                    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    with open(path, 'wb') as fh:
                        fh.write(resp.content)
                    Image.open(path).verify()
                    return item_name, path
            except:
                continue
    except Exception as e:
        print(f'  x {item_name}: {e}')
    return item_name, None

@app.route("/")
@login_required
def index():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(
            or_(User.email == identifier, User.username == identifier)
        ).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("home"))
        flash("Invalid email/username or password", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if User.query.filter_by(email=email).first():
            flash("Email already registered", "error")
        elif User.query.filter_by(username=username).first():
            flash("Username already taken", "error")
        else:
            user = User(
                username=username,
                email=email,
                password=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("home"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/home")
@login_required
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    photo    = request.files["photo"]
    gender   = request.form["gender"]
    occasion = request.form["occasion"]

    if not photo.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        return "Invalid file format"

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], photo.filename)
    photo.save(filepath)

    # ── NEW: Gemini-powered skin tone detection (with pixel fallback) ──
    skin_tone = detect_skin_tone(filepath)

    # ── AI text recommendations (skin tone now has 6 Indian labels) ──
    ai_prompt = f"""
    User Skin Tone: {skin_tone}, Gender: {gender}, Occasion: {occasion}

    You are an expert Indian fashion stylist. Generate a structured fashion styling
    recommendation tailored to Indian skin tones and Indian fashion sensibilities.

    Use <h3> for headings, <ul><li> for lists, <strong> for highlights.

    Sections:
    1. Suitable Color Palette (mention specific Indian color names where relevant e.g. Haldi yellow, Mehndi green, Kumkum red)
    2. Complete Outfit Combination (include Indian garment options where relevant)
    3. Accessories
    4. Hairstyle Suggestion
    5. Explanation (why these colors work for {skin_tone} skin tone)
    6. Sustainability Score out of 10
    7. Confidence Score out of 100

    Be professional, warm, and India-aware in your recommendations.
    """
    resp = _groq_completion(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": ai_prompt}]
    )
    if resp and getattr(resp, "choices", None):
        ai_output = resp.choices[0].message.content
    else:
        ai_output = "<p>Style suggestions are temporarily unavailable. Using local fallbacks.</p>"

    # Convert markdown headings ### to <h3> FIRST (must happen before bold/italic)
    ai_output = re.sub(r'^###\s*(.+)$', r'<h3>\1</h3>', ai_output, flags=re.MULTILINE)
    ai_output = re.sub(r'^##\s*(.+)$',  r'<h3>\1</h3>', ai_output, flags=re.MULTILINE)
    # Convert markdown bold/italic to HTML
    ai_output = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', ai_output)
    ai_output = re.sub(r'\*\*(.+?)\*\*',     r'<strong>\1</strong>',          ai_output)
    ai_output = re.sub(r'\*([^*\n]+?)\*',    r'<em>\1</em>',                  ai_output)
    # Convert newlines to <br> so line breaks render in HTML
    ai_output = re.sub(r'\n', '<br>', ai_output)

    # Get clothing items + images
    clothing_items = get_clothing_items(gender, occasion, skin_tone)
    base = os.path.splitext(photo.filename)[0]
    ordered = []
    for i, it in enumerate(clothing_items):
        name, path = fetch_item_image(it["item"], it["search"], f"item{i}_{base}.jpg")
        ordered.append({"item": name, "image": path})
        time.sleep(1)

    # Save to database
    analysis = Analysis(
        user_id    = current_user.id,
        gender     = gender,
        occasion   = occasion,
        skin_tone  = skin_tone,
        image_path = filepath,
        ai_output  = ai_output,
        items_json = json.dumps(ordered)
    )
    db.session.add(analysis)
    db.session.commit()

    sust_score, conf_score = extract_scores(ai_output)
    return render_template(
        "result.html",
        image_path     = filepath,
        clothing_items = ordered,
        skin_tone      = skin_tone,
        ai_output      = ai_output,
        gender         = gender,
        occasion       = occasion,
        analysis_id    = analysis.id,
        sust_score     = sust_score,
        conf_score     = conf_score
    )


@app.route("/history")
@login_required
def history():
    tab   = request.args.get("tab", "all")
    query = Analysis.query.filter_by(user_id=current_user.id)
    if tab == "favourites":
        query = query.filter_by(is_favourite=True)
    analyses = query.order_by(Analysis.created_at.desc()).all()
    return render_template("history.html", analyses=analyses, tab=tab)


@app.route("/history/favourite/<int:analysis_id>", methods=["POST"])
@login_required
def toggle_favourite(analysis_id):
    a = db.get_or_404(Analysis, analysis_id)
    if a.user_id != current_user.id:
        return "Unauthorized", 403
    a.is_favourite = not a.is_favourite
    db.session.commit()
    return redirect(request.referrer or url_for("history"))


@app.route("/history/delete/<int:analysis_id>", methods=["POST"])
@login_required
def delete_analysis(analysis_id):
    a = db.get_or_404(Analysis, analysis_id)
    if a.user_id != current_user.id:
        return "Unauthorized", 403
    db.session.delete(a)
    db.session.commit()
    return redirect(request.referrer or url_for("history"))


@app.route("/history/clear", methods=["POST"])
@login_required
def clear_history():
    Analysis.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return redirect(url_for("history"))


@app.route("/history/<int:analysis_id>")
@login_required
def view_analysis(analysis_id):
    a = db.get_or_404(Analysis, analysis_id)
    if a.user_id != current_user.id:
        return "Unauthorized", 403
    items = json.loads(a.items_json) if a.items_json else []
    sust_score, conf_score = extract_scores(a.ai_output)
    return render_template(
        "result.html",
        image_path     = a.image_path,
        clothing_items = items,
        skin_tone      = a.skin_tone,
        ai_output      = a.ai_output,
        gender         = a.gender,
        occasion       = a.occasion,
        analysis_id    = a.id,
        sust_score     = sust_score,
        conf_score     = conf_score
    )


# ─── Section parser (replaces extract_section template filter) ───────────────
# Works on raw Groq output regardless of whether it used ###, <h3>, or "1." headings.

SECTION_KEYWORDS = {
    'Color Palette':  ['color palette', 'colour palette', 'suitable color'],
    'Outfit':         ['outfit combination', 'complete outfit', 'outfit combo'],
    'Accessories':    ['accessories', 'accessory'],
    'Hairstyle':      ['hairstyle', 'hair style', 'hair suggestion'],
    'Explanation':    ['explanation', 'color harmony', 'colour harmony'],
    'Sustainability': ['sustainability', 'sustainable'],
    'Confidence':     ['confidence'],
}

def parse_ai_sections(raw: str) -> dict:
    """
    Parse Groq's raw output (markdown OR html) into a clean dict:
    { 'Color Palette': '<p>...</p>', 'Outfit': '...', ... }

    Strategy:
    1. Normalise all heading styles (###, ##, <h3>, numbered "1.") to a
       sentinel  __HEADING__text__HEADING__
    2. Split on sentinels to get (heading, content) pairs
    3. Match each heading to our SECTION_KEYWORDS dict
    4. Convert remaining markdown in content to HTML
    """
    text = raw

    # Step 1a — convert <h3> tags to sentinel
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'__HEADING__\1__HEADING__', text,
                  flags=re.IGNORECASE | re.DOTALL)
    # Step 1b — convert ### / ## markdown headings to sentinel
    text = re.sub(r'(?m)^#{2,3}\s*(.+)$', r'__HEADING__\1__HEADING__', text)
    # Step 1c — convert numbered headings "1. Suitable Color Palette" at line start
    text = re.sub(r'(?m)^\d+\.\s+((?:Suitable |Complete |Color |Colour |Outfit |Accessories|Hairstyle|Explanation|Sustainability|Confidence).+)$',
                  r'__HEADING__\1__HEADING__', text)

    # Step 2 — split into chunks between headings
    chunks = re.split(r'__HEADING__(.+?)__HEADING__', text)
    # chunks = [pre_text, heading1, content1, heading2, content2, ...]

    sections = {}
    i = 1
    while i < len(chunks) - 1:
        heading = chunks[i].strip().lower()
        heading = re.sub(r'^\d+\.?\s*', '', heading)  # strip leading numbers
        content = chunks[i + 1] if i + 1 < len(chunks) else ''

        # Match to a section key
        for key, kws in SECTION_KEYWORDS.items():
            if any(kw in heading for kw in kws):
                # Convert remaining markdown in content
                c = content
                c = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', c)
                c = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', c)
                c = re.sub(r'\*([^*\n]+?)\*', r'<em>\1</em>', c)
                # Convert bare newlines to <br>
                c = re.sub(r'\n', '<br>', c)
                # Trim any leading/trailing breaks
                c = c.strip('<br>').strip()
                sections[key] = c
                break
        i += 2

    return sections


@app.template_filter('extract_section')
def extract_section(ai_output, section_name):
    """Legacy template filter — kept so result.html doesn't need changes."""
    sections = parse_ai_sections(ai_output)
    for key in sections:
        if key.lower() in section_name.lower() or section_name.lower() in key.lower():
            return sections[key]
    # Last resort: return a trimmed version so it's never the full dump
    return '<em>Section not found.</em>'


def extract_scores(ai_output):
    """Extract sustainability and confidence scores from AI HTML output."""
    text = re.sub(r'<[^>]+>', ' ', ai_output)
    sust, conf = 8, 87
    m = re.search(r'sustainability[^0-9]*(\d+)\s*(?:out of|/)\s*10', text, re.IGNORECASE)
    if m: sust = min(int(m.group(1)), 10)
    m = re.search(r'(\d+)\s*(?:out of|/)\s*10[^0-9]*sustain', text, re.IGNORECASE)
    if m: sust = min(int(m.group(1)), 10)
    m = re.search(r'confidence[^0-9]*(\d+)\s*(?:out of|/)\s*100', text, re.IGNORECASE)
    if m: conf = min(int(m.group(1)), 100)
    m = re.search(r'(\d+)\s*(?:out of|/)\s*100[^0-9]*confidence', text, re.IGNORECASE)
    if m: conf = min(int(m.group(1)), 100)
    return sust, conf


# ─── Wardrobe Routes ──────────────────────────────────────
@app.route("/wardrobe")
@login_required
def wardrobe():
    items = WardrobeItem.query.filter_by(user_id=current_user.id).order_by(WardrobeItem.created_at.desc()).all()
    return render_template("wardrobe.html", items=items)


@app.route("/wardrobe/add", methods=["POST"])
@login_required
def wardrobe_add():
    name       = request.form.get("name", "").strip()
    category   = request.form.get("category", "Other")
    color      = request.form.get("color", "").strip()
    photo      = request.files.get("photo")
    image_path = None
    if photo and photo.filename:
        fname = f"ward_{current_user.id}_{int(time.time())}_{photo.filename}"
        fpath = os.path.join(app.config["UPLOAD_FOLDER"], fname)
        photo.save(fpath)
        image_path = fpath
    item = WardrobeItem(user_id=current_user.id, name=name, category=category,
                        color=color, image_path=image_path)
    db.session.add(item)
    db.session.commit()
    return redirect(url_for("wardrobe"))


@app.route("/wardrobe/delete/<int:item_id>", methods=["POST"])
@login_required
def wardrobe_delete(item_id):
    item = db.get_or_404(WardrobeItem, item_id)
    if item.user_id != current_user.id:
        return "Unauthorized", 403
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("wardrobe"))


@app.route("/wardrobe/suggest", methods=["POST"])
@login_required
def wardrobe_suggest():
    occasion = request.form.get("occasion", "Casual")
    items    = WardrobeItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        return redirect(url_for("wardrobe"))

    wardrobe_list = "\n".join(
        f"- {it.name} ({it.category}, {it.color})" for it in items
    )
    prompt = f"""You are a fashion stylist. The user has these clothes in their wardrobe:
{wardrobe_list}

Occasion: {occasion}

Suggest exactly 3 outfit combinations using ONLY items from the list above.
Respond ONLY with a valid JSON array. No markdown, no explanation.
Each outfit: {{"title": "Outfit name", "outfit_items": ["item name 1", "item name 2"], "tip": "one short styling tip"}}"""

    resp = _groq_completion(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    if resp and getattr(resp, "choices", None):
        raw = re.sub(r"```json|```", "", resp.choices[0].message.content.strip()).strip()
        try:
            suggestions = json.loads(raw)[:3]
        except:
            suggestions = []
    else:
        suggestions = []

    items_map = {it.name.lower(): it for it in items}
    return render_template("wardrobe.html", items=items, suggestions=suggestions,
                           occasion=occasion, items_map=items_map)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        from sqlalchemy import text, inspect
        inspector = inspect(db.engine)
        cols = [c["name"] for c in inspector.get_columns("analysis")]
        if "is_favourite" not in cols:
            with db.engine.connect() as con:
                con.execute(text("ALTER TABLE analysis ADD COLUMN is_favourite BOOLEAN DEFAULT 0"))
                con.commit()
            print("Migrated: added is_favourite column")
    app.run(debug=True)

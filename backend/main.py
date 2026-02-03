import os
import re
import logging
import sqlite3
import csv
import io
import hashlib
import secrets
import httpx
from datetime import datetime
from typing import List, Optional, Dict
from collections import defaultdict, Counter
import time as time_module
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field, validator
import anthropic
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from user_agents import parse as parse_ua
from urllib.parse import urlparse
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Faith Companion API")

# ============== RATE LIMITING ==============
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW = 3600
rate_limit_store: Dict[str, List[float]] = defaultdict(list)

_last_rate_limit_cleanup = 0.0

def check_rate_limit(ip_address: str) -> tuple[bool, int, int]:
    global _last_rate_limit_cleanup
    now = time_module.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Periodically purge stale IPs from the store (every 10 minutes)
    if now - _last_rate_limit_cleanup > 600:
        stale_ips = [ip for ip, times in rate_limit_store.items() if not any(t > window_start for t in times)]
        for ip in stale_ips:
            del rate_limit_store[ip]
        _last_rate_limit_cleanup = now

    rate_limit_store[ip_address] = [t for t in rate_limit_store[ip_address] if t > window_start]
    requests_made = len(rate_limit_store[ip_address])
    remaining = max(0, RATE_LIMIT_REQUESTS - requests_made)
    if requests_made >= RATE_LIMIT_REQUESTS:
        oldest = min(rate_limit_store[ip_address]) if rate_limit_store[ip_address] else now
        return False, 0, int(oldest + RATE_LIMIT_WINDOW - now)
    rate_limit_store[ip_address].append(now)
    return True, remaining - 1, RATE_LIMIT_WINDOW

# ============== SPAM DETECTION ==============
SPAM_PATTERNS = [r"(buy|sell|cheap|discount|click here)", r"(viagra|cialis|casino|lottery)", r"(http[s]?://(?!fc\.catholic\.ng))", r"(.{1,3})\1{10,}"]

def is_gibberish(message: str) -> bool:
    """Detect keyboard-mash gibberish messages."""
    text = message.strip()
    if len(text) < 10:
        return False

    # Check for very long stretches without spaces (normal words are short)
    words = text.split()
    if words:
        longest_word = max(len(w) for w in words)
        avg_word_len = sum(len(w) for w in words) / len(words)
        # Normal text rarely has words >25 chars; gibberish is often one long string
        if longest_word > 30:
            return True
        # Average word length in English is ~5; gibberish skews much higher
        if avg_word_len > 15 and len(words) < 5:
            return True

    # Check consonant-to-vowel ratio (gibberish tends to be consonant-heavy)
    alpha_chars = re.findall(r'[a-zA-Z]', text)
    if len(alpha_chars) > 10:
        vowels = sum(1 for c in alpha_chars if c.lower() in 'aeiou')
        vowel_ratio = vowels / len(alpha_chars)
        # Normal English has ~38% vowels; gibberish is often <15%
        if vowel_ratio < 0.12:
            return True

    # Check for repeated character sequences (e.g., "dkdkdkdk", "ababab")
    if len(text) > 15:
        # Count unique bigrams vs total — gibberish has low diversity
        bigrams = [text[i:i+2].lower() for i in range(len(text) - 1)]
        if bigrams:
            unique_ratio = len(set(bigrams)) / len(bigrams)
            if unique_ratio < 0.25 and len(text) > 20:
                return True

    return False

def is_spam(message: str) -> bool:
    if any(re.search(p, message.lower()) for p in SPAM_PATTERNS):
        return True
    return is_gibberish(message)

# ============== FAQ CACHE (saves API calls) ==============
FAQ_CACHE = {
    "mass readings": "I'm sorry, I don't have access to daily Mass readings at this time. For today's readings, I recommend visiting Vatican News (vaticannews.va/en/word-of-the-day.html) or the USCCB website (bible.usccb.org/daily-bible-reading). Your parish bulletin may also have the readings listed.",
    "today readings": "I'm sorry, I don't have access to daily Mass readings at this time. For today's readings, I recommend visiting Vatican News (vaticannews.va/en/word-of-the-day.html) or the USCCB website (bible.usccb.org/daily-bible-reading). Your parish bulletin may also have the readings listed.",
    "daily readings": "I'm sorry, I don't have access to daily Mass readings at this time. For today's readings, I recommend visiting Vatican News (vaticannews.va/en/word-of-the-day.html) or the USCCB website (bible.usccb.org/daily-bible-reading). Your parish bulletin may also have the readings listed.",
    "gospel today": "I'm sorry, I don't have access to daily Mass readings at this time. For today's Gospel, I recommend visiting Vatican News (vaticannews.va/en/word-of-the-day.html) or the USCCB website (bible.usccb.org/daily-bible-reading).",
    "mass schedule": "I don't have access to parish Mass schedules, as these vary by location. Please contact your local parish directly or visit the Diocese of Port Harcourt website (catholicdioceseofportharcourt.com) for information about Mass times in your area.",
    "mass times": "I don't have access to parish Mass schedules, as these vary by location. Please contact your local parish directly or visit the Diocese of Port Harcourt website (catholicdioceseofportharcourt.com) for information about Mass times in your area.",
    "what time is mass": "I don't have access to parish Mass schedules, as these vary by location. Please contact your local parish directly or visit the Diocese of Port Harcourt website (catholicdioceseofportharcourt.com) for information about Mass times in your area.",
    "what is this": "I am Faith Companion, your AI guide to Catholic teaching from the Diocese of Port Harcourt. I can help with questions about doctrine, Scripture, sacraments, and living the faith. How can I help you?",
    "who are you": "I am Faith Companion, your AI guide to Catholic teaching from the Diocese of Port Harcourt. I can help with questions about doctrine, Scripture, sacraments, and living the faith. How can I help you?",
    "what can you do": "I can help you understand Catholic teaching, explore Scripture, learn about sacraments, and answer faith questions. I draw from the Catechism, Vatican II, Canon Law, and papal documents. What would you like to know?",
    "hello": "Hello! I'm Faith Companion, here to help you explore the Catholic faith. What question can I help you with today?",
    "hi": "Hello! I'm Faith Companion, here to help you explore the Catholic faith. What question can I help you with today?",
    "hey": "Hello! I'm Faith Companion, here to help you explore the Catholic faith. What question can I help you with today?",
    "help": "I can help with: Catholic doctrine, Scripture, sacraments, prayer, moral teaching, Church history, and more. Just ask your question!",
}

def get_cached_response(message: str) -> Optional[str]:
    msg = message.lower().strip().rstrip("?")
    return FAQ_CACHE.get(msg)

# ============== TOPIC CATEGORIZATION ==============
TOPIC_KEYWORDS = {
    "Sacraments": ["baptism", "eucharist", "communion", "confession", "reconciliation", "confirmation", "marriage", "holy orders", "anointing", "sacrament"],
    "Doctrine": ["trinity", "incarnation", "resurrection", "salvation", "grace", "sin", "heaven", "hell", "purgatory", "redemption", "original sin", "immaculate conception"],
    "Prayer": ["prayer", "rosary", "novena", "mass", "liturgy of the hours", "adoration", "worship", "intercession", "petition", "praise"],
    "Morality": ["morality", "ethics", "sin", "virtue", "commandments", "conscience", "natural law", "moral", "right", "wrong", "good", "evil"],
    "Scripture": ["bible", "gospel", "scripture", "old testament", "new testament", "psalm", "matthew", "mark", "luke", "john", "acts", "revelation", "genesis", "exodus"],
    "Church History": ["council", "vatican", "trent", "nicaea", "reformation", "early church", "fathers", "doctors", "tradition", "papal"],
    "Liturgy": ["liturgy", "mass", "eucharistic", "divine office", "lectionary", "missal", "altar", "vestments", "incense", "ritual"],
    "Saints": ["saint", "mary", "joseph", "apostle", "martyr", "virgin mary", "blessed virgin", "our lady", "patron"],
}

def categorize_topic(query: str) -> str:
    """Categorize query based on keywords."""
    query_lower = query.lower()
    scores = {}

    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in query_lower)
        if score > 0:
            scores[topic] = score

    if scores:
        return max(scores, key=scores.get)
    return "General"

# ============== REFERRER PARSING ==============
def parse_referrer(referrer: Optional[str]) -> str:
    """Extract domain from referrer URL."""
    if not referrer:
        return ""
    try:
        parsed = urlparse(referrer)
        domain = parsed.netloc or parsed.path
        return domain if domain else ""
    except (ValueError, AttributeError):
        return ""

# ============== TOKEN COST CALCULATION ==============
# Haiku pricing: $0.25/MTok input, $1.25/MTok output
HAIKU_INPUT_COST_PER_MTOK = 0.25
HAIKU_OUTPUT_COST_PER_MTOK = 1.25

def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated cost in USD."""
    input_cost = (input_tokens / 1_000_000) * HAIKU_INPUT_COST_PER_MTOK
    output_cost = (output_tokens / 1_000_000) * HAIKU_OUTPUT_COST_PER_MTOK
    return input_cost + output_cost

# ============== INPUT VALIDATION ==============
MAX_MESSAGE_LENGTH = 2000
MIN_MESSAGE_LENGTH = 2

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=MIN_MESSAGE_LENGTH, max_length=MAX_MESSAGE_LENGTH)
    conversation_history: Optional[List[dict]] = []
    session_id: Optional[str] = None
    # Advanced user tracking
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None
    language: Optional[str] = None
    connection_type: Optional[str] = None  # slow-2g, 2g, 3g, 4g, wifi
    color_scheme: Optional[str] = None  # dark, light
    input_type: Optional[str] = None  # touch, mouse
    session_duration_ms: Optional[int] = None
    time_since_last_msg_ms: Optional[int] = None

class ChatResponse(BaseModel):
    response: str
    sources: List[str] = []


class SpiritualDirectionRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = None
    email: Optional[str] = None
    request_type: str = Field(..., pattern="^(spiritual_direction|confession|both)$")
    message: Optional[str] = Field(None, max_length=1000)

class FeedbackRequest(BaseModel):
    chat_log_id: int
    feedback_type: str = Field(..., pattern="^(positive|negative)$")
    comment: Optional[str] = None

# ============== AUTH ==============
security = HTTPBasic()
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD environment variable must be set")

def verify_admin(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()
    
    # Check rate limit
    allowed, reset_time = check_admin_rate_limit(ip)
    if not allowed:
        logger.warning(f"Admin login rate limited for IP {ip}. Reset in {reset_time}s")
        raise HTTPException(status_code=429, detail=f"Too many login attempts. Try again in {reset_time // 60} minutes.", headers={"Retry-After": str(reset_time)})
    
    if not (secrets.compare_digest(credentials.username.encode(), ADMIN_USERNAME.encode()) and secrets.compare_digest(credentials.password.encode(), ADMIN_PASSWORD.encode())):
        record_failed_admin_login(ip)
        raise HTTPException(status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Basic"})
    
    clear_admin_login_attempts(ip)
    return credentials.username

app.add_middleware(CORSMiddleware, allow_origins=["https://fc.catholic.ng", "https://www.fc.catholic.ng"], allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])

vectorstore = None
client = None
ANALYTICS_DB = "/app/data/analytics.db"

# OPTIMIZED: Shorter system prompt (~200 tokens vs ~400)
SYSTEM_PROMPT = """IMPORTANT CURRENT FACTS:
- The current Pope is Pope Leo XIV (elected May 2025), NOT Pope Francis.
- The Diocese of Port Harcourt: Bishop Camillus Archibong Etokudoh retired April 9, 2025. Bishop Patrick Eluke is the current Apostolic Administrator.

You are Faith Companion, a Catholic faith assistant for the Diocese of Port Harcourt, Nigeria.

Guidelines:
- Ground answers in the Catechism (cite CCC numbers when possible)
- Include Scripture references
- Use Nigerian context and examples
- Be pastorally sensitive
- For personal guidance, suggest speaking with a priest
- If uncertain, say so
- Keep responses concise but complete
- Do NOT provide specific daily Mass readings (First Reading, Psalm, Gospel, etc.) as these change daily and your information may be outdated or incorrect. Instead, direct users to Vatican News (vaticannews.va/en/word-of-the-day.html) or USCCB (bible.usccb.org/daily-bible-reading) for current readings.
- For Mass schedules, direct users to their local parish.
- Do NOT mention mitigating factors for sin (such as habit, immaturity, anxiety, or psychological conditions). This evaluation belongs to the confessor in the confessional, not to general spiritual advice. Mentioning these can enable people to excuse their sins rather than truly repent.
- Always emphasize the Sacrament of Confession (Reconciliation) as the ordinary and expected means of forgiveness for mortal sins. While perfect contrition exists as an extraordinary remedy, do not present it as an easy alternative. In Nigeria, priests are readily available in parishes across the country. Gently challenge excuses about being unable to reach a priest, and firmly encourage the person to make the effort to go to Confession as soon as possible."""

def init_analytics_db():
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    # Spiritual direction requests table
    cursor.execute("""CREATE TABLE IF NOT EXISTS spiritual_direction_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        name TEXT,
        phone TEXT,
        email TEXT,
        request_type TEXT,
        message TEXT,
        city TEXT,
        country TEXT,
        status TEXT DEFAULT 'pending',
        notes TEXT,
        followed_up_at TEXT
    )""")
    conn.commit()
    conn.close()

    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    # Create chat_logs table with all new columns
    cursor.execute("""CREATE TABLE IF NOT EXISTS chat_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        session_id TEXT,
        user_query TEXT,
        ai_response TEXT,
        response_time_ms INTEGER,
        ip_address TEXT,
        country TEXT,
        country_code TEXT,
        region TEXT,
        region_name TEXT,
        city TEXT,
        zip_code TEXT,
        latitude REAL,
        longitude REAL,
        timezone TEXT,
        isp TEXT,
        user_agent TEXT,
        browser TEXT,
        browser_version TEXT,
        os TEXT,
        os_version TEXT,
        device_type TEXT,
        device_brand TEXT,
        device_model TEXT,
        is_mobile INTEGER,
        is_tablet INTEGER,
        is_pc INTEGER,
        is_bot INTEGER,
        sources TEXT,
        cached INTEGER DEFAULT 0,
        topic TEXT,
        feedback_given INTEGER DEFAULT 0,
        messages_in_session INTEGER DEFAULT 1,
        is_return_visitor INTEGER DEFAULT 0,
        session_start_time TEXT,
        referrer TEXT,
        avg_similarity_score REAL,
        input_tokens INTEGER,
        output_tokens INTEGER,
        estimated_cost REAL
    )""")

    # Create feedback table
    cursor.execute("""CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_log_id INTEGER,
        feedback_type TEXT,
        comment TEXT,
        timestamp TEXT,
        FOREIGN KEY (chat_log_id) REFERENCES chat_logs(id)
    )""")

    # Add new columns to existing tables (if they don't exist)
    new_columns = [
        ("topic", "TEXT"),
        ("feedback_given", "INTEGER DEFAULT 0"),
        ("messages_in_session", "INTEGER DEFAULT 1"),
        ("is_return_visitor", "INTEGER DEFAULT 0"),
        ("session_start_time", "TEXT"),
        ("referrer", "TEXT"),
        ("avg_similarity_score", "REAL"),
        ("input_tokens", "INTEGER"),
        ("output_tokens", "INTEGER"),
        ("estimated_cost", "REAL"),
        # Advanced user tracking columns
        ("screen_width", "INTEGER"),
        ("screen_height", "INTEGER"),
        ("language", "TEXT"),
        ("connection_type", "TEXT"),
        ("color_scheme", "TEXT"),
        ("input_type", "TEXT"),
        ("session_duration_ms", "INTEGER"),
        ("time_since_last_msg_ms", "INTEGER"),
    ]

    for col, typ in new_columns:
        try:
            cursor.execute(f"ALTER TABLE chat_logs ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Create indexes for common query patterns
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_timestamp ON chat_logs(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_session_id ON chat_logs(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_ip_address ON chat_logs(ip_address)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_chat_log_id ON feedback(chat_log_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp)")

    conn.commit()
    conn.close()
    logger.info("Analytics database initialized with enhanced features")

def get_geo_location(ip_address: str, retries: int = 2) -> dict:
    """Get geographic location from IP address with retry logic."""
    # Skip private/local IPs (but don't skip 172.x mobile IPs - only 172.16-31 are private)
    if ip_address in ["127.0.0.1", "localhost", "unknown"]:
        return {}
    if ip_address.startswith("192.168.") or ip_address.startswith("10."):
        return {}
    # Only skip private 172.16.0.0 - 172.31.255.255 range
    if ip_address.startswith("172."):
        try:
            second_octet = int(ip_address.split(".")[1])
            if 16 <= second_octet <= 31:
                return {}
        except (ValueError, IndexError):
            pass

    for attempt in range(retries):
        try:
            response = httpx.get(
                f"http://ip-api.com/json/{ip_address}?fields=status,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp",
                timeout=5.0  # Increased from 3s to 5s
            )
            data = response.json()
            if data.get("status") == "success":
                result = {
                    "country": data.get("country", ""),
                    "country_code": data.get("countryCode", ""),
                    "region": data.get("region", ""),
                    "region_name": data.get("regionName", ""),
                    "city": data.get("city", ""),
                    "zip_code": data.get("zip", ""),
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon"),
                    "timezone": data.get("timezone", ""),
                    "isp": data.get("isp", "")
                }
                logger.info(f"GeoIP success for {ip_address}: {result.get('city')}, {result.get('country')}")
                return result
            else:
                logger.warning(f"GeoIP lookup failed for {ip_address}: {data.get('message', 'unknown error')}")
        except httpx.TimeoutException:
            logger.warning(f"GeoIP timeout for {ip_address} (attempt {attempt + 1}/{retries})")
            if attempt < retries - 1:
                time_module.sleep(0.5)  # Brief delay before retry
        except Exception as e:
            logger.error(f"GeoIP error for {ip_address}: {type(e).__name__}: {e}")
            break  # Don't retry on non-timeout errors

    return {}

def get_session_info(session_id: str, ip_address: str) -> dict:
    """Get session information including message count and return visitor status."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    # Count messages in current session
    cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE session_id = ?", (session_id,))
    messages_in_session = cursor.fetchone()[0] + 1  # +1 for current message

    # Check if return visitor (has previous sessions from this IP)
    cursor.execute("""
        SELECT COUNT(DISTINCT session_id)
        FROM chat_logs
        WHERE ip_address = ? AND session_id != ?
    """, (ip_address, session_id))
    previous_sessions = cursor.fetchone()[0]
    is_return_visitor = 1 if previous_sessions > 0 else 0

    # Get session start time
    cursor.execute("""
        SELECT MIN(timestamp)
        FROM chat_logs
        WHERE session_id = ?
    """, (session_id,))
    result = cursor.fetchone()
    session_start_time = result[0] if result[0] else datetime.utcnow().isoformat()

    conn.close()

    return {
        "messages_in_session": messages_in_session,
        "is_return_visitor": is_return_visitor,
        "session_start_time": session_start_time
    }

def log_chat_interaction(session_id, user_query, ai_response, response_time_ms, ip_address,
                         user_agent_str, sources, cached=False, topic="General",
                         referrer="", avg_similarity_score=None, input_tokens=0,
                         output_tokens=0, estimated_cost=0.0,
                         screen_width=None, screen_height=None, language=None,
                         connection_type=None, color_scheme=None, input_type=None,
                         session_duration_ms=None, time_since_last_msg_ms=None):
    try:
        ua = parse_ua(user_agent_str)
        device_type = "Mobile" if ua.is_mobile else "Tablet" if ua.is_tablet else "PC"
        geo = get_geo_location(ip_address)
        session_info = get_session_info(session_id, ip_address)

        conn = sqlite3.connect(ANALYTICS_DB)
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO chat_logs (
            timestamp, session_id, user_query, ai_response, response_time_ms, ip_address,
            country, country_code, region, region_name, city, zip_code, latitude, longitude,
            timezone, isp, user_agent, browser, browser_version, os, os_version, device_type,
            device_brand, device_model, is_mobile, is_tablet, is_pc, is_bot, sources, cached,
            topic, messages_in_session, is_return_visitor, session_start_time, referrer,
            avg_similarity_score, input_tokens, output_tokens, estimated_cost,
            screen_width, screen_height, language, connection_type, color_scheme,
            input_type, session_duration_ms, time_since_last_msg_ms
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (datetime.utcnow().isoformat(), session_id, user_query, ai_response,
             response_time_ms, ip_address, geo.get("country",""), geo.get("country_code",""),
             geo.get("region",""), geo.get("region_name",""), geo.get("city",""),
             geo.get("zip_code",""), geo.get("latitude"), geo.get("longitude"),
             geo.get("timezone",""), geo.get("isp",""), user_agent_str[:300], ua.browser.family,
             ua.browser.version_string, ua.os.family, ua.os.version_string, device_type,
             ua.device.brand or "Unknown", ua.device.model or "Unknown",
             1 if ua.is_mobile else 0, 1 if ua.is_tablet else 0, 1 if ua.is_pc else 0,
             1 if ua.is_bot else 0, ",".join(sources), 1 if cached else 0, topic,
             session_info["messages_in_session"], session_info["is_return_visitor"],
             session_info["session_start_time"], referrer, avg_similarity_score,
             input_tokens, output_tokens, estimated_cost,
             screen_width, screen_height, language, connection_type, color_scheme,
             input_type, session_duration_ms, time_since_last_msg_ms))
        conn.commit()
        chat_id = cursor.lastrowid
        conn.close()
        return chat_id
    except Exception as e:
        logger.error(f"Failed to log: {e}")
        return None

def initialize_rag():
    global vectorstore
    docs_path, persist_dir = "/app/documents", "/app/data/chroma_db"
    if os.path.exists(persist_dir) and os.listdir(persist_dir):
        logger.info("Loading existing vector store...")
        vectorstore = Chroma(persist_directory=persist_dir, embedding_function=HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2"))
        logger.info(f"Loaded {vectorstore._collection.count()} documents")
        return
    logger.info("Building vector store...")
    documents = []
    if os.path.exists(docs_path):
        for f in os.listdir(docs_path):
            if f.endswith((".pdf", ".txt")):
                documents.extend((PyPDFLoader if f.endswith(".pdf") else TextLoader)(os.path.join(docs_path, f)).load())
    if not documents:
        logger.warning("No documents found in %s — RAG will be unavailable, using LLM-only mode", docs_path)
        return
    chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(documents)
    vectorstore = Chroma.from_documents(chunks, HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2"), persist_directory=persist_dir)
    vectorstore.persist()

@app.on_event("startup")
async def startup_event():
    global client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable must be set")
    client = anthropic.Anthropic(api_key=api_key)
    init_analytics_db()
    initialize_rag()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": "claude-3-haiku"}

@app.post("/chat")
async def chat(request: ChatRequest, req: Request):
    global vectorstore, client

    ip = req.headers.get("X-Forwarded-For", req.client.host if req.client else "unknown").split(",")[0].strip()

    allowed, remaining, reset = check_rate_limit(ip)
    if not allowed:
        return JSONResponse(status_code=429, content={"error": "Rate limit exceeded", "error_code": "RATE_LIMITED", "details": {"reset_minutes": round(reset/60), "limit": RATE_LIMIT_REQUESTS}})

    if is_spam(request.message):
        return JSONResponse(status_code=400, content={"error": "Message flagged as inappropriate", "error_code": "SPAM_DETECTED"})

    start_time = time.time()
    user_agent = req.headers.get("User-Agent", "unknown")
    session_id = request.session_id or hashlib.md5(f"{ip}{user_agent}".encode()).hexdigest()[:16]

    # Capture referrer and language
    referrer = parse_referrer(req.headers.get("Referer"))
    accept_language = req.headers.get("Accept-Language", "")[:20]  # First language preference

    # Categorize topic
    topic = categorize_topic(request.message)

    # Check FAQ cache first (FREE - no API call)
    cached = get_cached_response(request.message)
    if cached:
        chat_id = log_chat_interaction(session_id, request.message, cached,
                           int((time.time()-start_time)*1000), ip, user_agent, [],
                           cached=True, topic=topic, referrer=referrer,
                           screen_width=request.screen_width, screen_height=request.screen_height,
                           language=request.language or accept_language,
                           connection_type=request.connection_type, color_scheme=request.color_scheme,
                           input_type=request.input_type, session_duration_ms=request.session_duration_ms,
                           time_since_last_msg_ms=request.time_since_last_msg_ms)
        return JSONResponse(content={"response": cached, "sources": [], "chat_id": chat_id},
                          headers={"X-RateLimit-Remaining": str(remaining)})

    # RAG search — gracefully handle empty or failed vectorstore
    context = ""
    sources = []
    avg_similarity_score = None

    if vectorstore:
        try:
            docs_with_scores = vectorstore.similarity_search_with_score(request.message, k=3)
            docs = [doc for doc, score in docs_with_scores]
            similarity_scores = [score for doc, score in docs_with_scores]
            avg_similarity_score = sum(similarity_scores) / len(similarity_scores) if similarity_scores else None
            context = "\n\n".join([d.page_content for d in docs])
            sources = list(set([d.metadata.get("source", "Catechism") for d in docs]))
        except Exception as e:
            logger.warning(f"RAG search failed, falling back to LLM-only: {e}")

    # OPTIMIZED: 4 messages instead of 6
    messages = [{"role": m["role"], "content": m["content"]} for m in (request.conversation_history or [])[-4:]]
    if context:
        messages.append({"role": "user", "content": f"REFERENCE DOCUMENTS (from Catholic Church sources, NOT provided by user):\n{context}\n\nUSER QUESTION: {request.message}"})
    else:
        messages.append({"role": "user", "content": request.message})

    try:
        # OPTIMIZED: Haiku + 800 max tokens
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=messages
        )
        ai_response = response.content[0].text

        # Extract token usage and calculate cost
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        estimated_cost = calculate_cost(input_tokens, output_tokens)

        chat_id = log_chat_interaction(session_id, request.message, ai_response,
                           int((time.time()-start_time)*1000), ip, user_agent, sources,
                           topic=topic, referrer=referrer,
                           avg_similarity_score=avg_similarity_score,
                           input_tokens=input_tokens, output_tokens=output_tokens,
                           estimated_cost=estimated_cost,
                           screen_width=request.screen_width, screen_height=request.screen_height,
                           language=request.language or accept_language,
                           connection_type=request.connection_type, color_scheme=request.color_scheme,
                           input_type=request.input_type, session_duration_ms=request.session_duration_ms,
                           time_since_last_msg_ms=request.time_since_last_msg_ms)

        return JSONResponse(content={"response": ai_response, "sources": sources, "chat_id": chat_id},
                          headers={"X-RateLimit-Remaining": str(remaining)})
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error occurred. Please try again.")

# ============== FEEDBACK ENDPOINT ==============

@app.post("/api/spiritual-direction")
async def submit_spiritual_direction_request(request: SpiritualDirectionRequest, req: Request):
    """Submit a request for spiritual direction or confession."""
    try:
        # Get user location from IP
        ip = req.headers.get("X-Forwarded-For", req.client.host if req.client else "unknown").split(",")[0].strip()

        geo = get_geo_location(ip)
        city = geo.get("city")
        country = geo.get("country")

        conn = sqlite3.connect(ANALYTICS_DB)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO spiritual_direction_requests
            (timestamp, name, phone, email, request_type, message, city, country, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            datetime.utcnow().isoformat(),
            request.name,
            request.phone,
            request.email,
            request.request_type,
            request.message,
            city,
            country
        ))
        conn.commit()
        request_id = cursor.lastrowid
        conn.close()

        return {"success": True, "id": request_id, "message": "Your request has been submitted. Fr Kennedy will contact you soon."}
    except Exception as e:
        logger.error(f"Error submitting spiritual direction request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/spiritual-direction")
async def get_spiritual_direction_requests(status: str = None, username: str = Depends(verify_admin)):
    """Get all spiritual direction requests (admin only)."""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if status:
            cursor.execute("""
                SELECT * FROM spiritual_direction_requests
                WHERE status = ?
                ORDER BY timestamp DESC
            """, (status,))
        else:
            cursor.execute("""
                SELECT * FROM spiritual_direction_requests
                ORDER BY timestamp DESC
            """)

        requests = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {"requests": requests}
    except Exception as e:
        logger.error(f"Error getting spiritual direction requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/admin/spiritual-direction/{request_id}")
async def update_spiritual_direction_request(request_id: int, status: str, notes: str = None, username: str = Depends(verify_admin)):
    """Update a spiritual direction request status (admin only)."""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        cursor = conn.cursor()

        if status == 'followed_up':
            cursor.execute("""
                UPDATE spiritual_direction_requests
                SET status = ?, notes = ?, followed_up_at = ?
                WHERE id = ?
            """, (status, notes, datetime.utcnow().isoformat(), request_id))
        else:
            cursor.execute("""
                UPDATE spiritual_direction_requests
                SET status = ?, notes = ?
                WHERE id = ?
            """, (status, notes, request_id))

        conn.commit()
        conn.close()

        return {"success": True}
    except Exception as e:
        logger.error(f"Error updating spiritual direction request: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@app.delete("/api/admin/spiritual-direction/{request_id}")
async def delete_spiritual_direction_request(request_id: int, username: str = Depends(verify_admin)):
    """Delete a spiritual direction request (admin only)."""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM spiritual_direction_requests WHERE id = ?", (request_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()

        if deleted:
            return {"success": True, "message": "Request deleted"}
        else:
            raise HTTPException(status_code=404, detail="Request not found")
    except Exception as e:
        logger.error(f"Error deleting spiritual direction request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/spiritual-direction/export")
async def export_spiritual_direction_csv(username: str = Depends(verify_admin)):
    """Export all spiritual direction requests as CSV."""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, timestamp, name, phone, email, request_type, message,
                   city, country, status, notes, followed_up_at
            FROM spiritual_direction_requests
            ORDER BY timestamp DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(['ID', 'Date', 'Name', 'Phone', 'Email', 'Request Type', 'Message', 'City', 'Country', 'Status', 'Notes', 'Followed Up At'])

        # Data
        for row in rows:
            writer.writerow([
                row['id'],
                row['timestamp'],
                row['name'],
                row['phone'],
                row['email'] or '',
                row['request_type'],
                row['message'] or '',
                row['city'] or '',
                row['country'] or '',
                row['status'],
                row['notes'] or '',
                row['followed_up_at'] or ''
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=spiritual_direction_requests.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting spiritual direction requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """Submit feedback for a chat interaction."""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        cursor = conn.cursor()

        # Verify chat_log_id exists
        cursor.execute("SELECT id FROM chat_logs WHERE id = ?", (feedback.chat_log_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Chat log not found")

        # Insert feedback
        cursor.execute("""INSERT INTO feedback (chat_log_id, feedback_type, comment, timestamp)
                         VALUES (?, ?, ?, ?)""",
                      (feedback.chat_log_id, feedback.feedback_type,
                       feedback.comment, datetime.utcnow().isoformat()))

        # Update feedback_given flag
        cursor.execute("UPDATE chat_logs SET feedback_given = 1 WHERE id = ?",
                      (feedback.chat_log_id,))

        conn.commit()
        conn.close()

        return {"status": "success", "message": "Feedback submitted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail="Error submitting feedback")

# ============== ANALYTICS ENDPOINTS ==============

@app.get("/api/analytics/summary")
async def get_analytics_summary(username: str = Depends(verify_admin)):
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    # Basic stats
    cursor.execute("SELECT COUNT(*) FROM chat_logs")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT session_id) FROM chat_logs")
    unique = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(response_time_ms) FROM chat_logs")
    avg_time = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(cached) FROM chat_logs")
    cached = cursor.fetchone()[0] or 0

    # Device stats
    cursor.execute("SELECT device_type, COUNT(*) FROM chat_logs GROUP BY device_type")
    devices = dict(cursor.fetchall())

    # Browser stats
    cursor.execute("SELECT browser, COUNT(*) FROM chat_logs GROUP BY browser ORDER BY COUNT(*) DESC LIMIT 5")
    browsers = dict(cursor.fetchall())

    # Location stats
    cursor.execute("""SELECT country, region_name, city, COUNT(*)
                     FROM chat_logs WHERE country != ''
                     GROUP BY country, region_name, city
                     ORDER BY COUNT(*) DESC LIMIT 10""")
    locations = [{"country": r[0], "region": r[1], "city": r[2], "count": r[3]}
                for r in cursor.fetchall()]

    # Daily stats
    cursor.execute("""SELECT DATE(timestamp), COUNT(*)
                     FROM chat_logs
                     WHERE timestamp >= datetime('now', '-7 days')
                     GROUP BY DATE(timestamp)""")
    daily = [{"date": r[0], "count": r[1]} for r in cursor.fetchall()]

    # New metrics
    cursor.execute("SELECT AVG(messages_in_session) FROM chat_logs")
    avg_session_depth = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE is_return_visitor = 1")
    return_visitors = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(input_tokens), SUM(output_tokens), SUM(estimated_cost) FROM chat_logs")
    tokens_cost = cursor.fetchone()
    total_input_tokens = tokens_cost[0] or 0
    total_output_tokens = tokens_cost[1] or 0
    total_cost = tokens_cost[2] or 0

    cursor.execute("SELECT COUNT(*) FROM feedback WHERE feedback_type = 'positive'")
    positive_feedback = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM feedback WHERE feedback_type = 'negative'")
    negative_feedback = cursor.fetchone()[0]

    conn.close()

    return {
        "total_chats": total,
        "unique_sessions": unique,
        "avg_response_time_ms": round(avg_time),
        "cached_responses": cached,
        "devices": devices,
        "browsers": browsers,
        "locations": locations,
        "daily_stats": daily,
        "avg_session_depth": round(avg_session_depth, 2),
        "return_visitors": return_visitors,
        "return_visitor_rate": round((return_visitors / total * 100) if total > 0 else 0, 2),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cost_usd": round(total_cost, 4),
        "positive_feedback": positive_feedback,
        "negative_feedback": negative_feedback
    }

@app.get("/api/analytics/feedback")
async def get_feedback_analytics(username: str = Depends(verify_admin)):
    """Get feedback summary statistics."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    # Overall feedback stats
    cursor.execute("SELECT COUNT(*) FROM feedback")
    total_feedback = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM feedback WHERE feedback_type = 'positive'")
    positive = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM feedback WHERE feedback_type = 'negative'")
    negative = cursor.fetchone()[0]

    # Recent feedback with comments
    cursor.execute("""
        SELECT f.id, f.chat_log_id, f.feedback_type, f.comment, f.timestamp,
               c.user_query, c.ai_response
        FROM feedback f
        JOIN chat_logs c ON f.chat_log_id = c.id
        ORDER BY f.timestamp DESC
        LIMIT 20
    """)
    recent_feedback = [{
        "id": r[0],
        "chat_log_id": r[1],
        "feedback_type": r[2],
        "comment": r[3],
        "timestamp": r[4],
        "user_query": r[5],
        "ai_response": r[6]
    } for r in cursor.fetchall()]

    # Feedback by topic
    cursor.execute("""
        SELECT c.topic, f.feedback_type, COUNT(*)
        FROM feedback f
        JOIN chat_logs c ON f.chat_log_id = c.id
        GROUP BY c.topic, f.feedback_type
        ORDER BY c.topic
    """)
    feedback_by_topic = {}
    for row in cursor.fetchall():
        topic = row[0] or "General"
        if topic not in feedback_by_topic:
            feedback_by_topic[topic] = {"positive": 0, "negative": 0}
        feedback_by_topic[topic][row[1]] = row[2]

    conn.close()

    return {
        "total_feedback": total_feedback,
        "positive": positive,
        "negative": negative,
        "satisfaction_rate": round((positive / total_feedback * 100) if total_feedback > 0 else 0, 2),
        "recent_feedback": recent_feedback,
        "feedback_by_topic": feedback_by_topic
    }

@app.get("/api/analytics/topics")
async def get_topic_analytics(username: str = Depends(verify_admin)):
    """Get topic distribution analytics."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    # Topic distribution
    cursor.execute("""
        SELECT topic, COUNT(*) as count
        FROM chat_logs
        GROUP BY topic
        ORDER BY count DESC
    """)
    topic_distribution = [{"topic": r[0] or "General", "count": r[1]}
                         for r in cursor.fetchall()]

    # Topic by device
    cursor.execute("""
        SELECT topic, device_type, COUNT(*)
        FROM chat_logs
        GROUP BY topic, device_type
        ORDER BY topic, COUNT(*) DESC
    """)
    topic_by_device = {}
    for row in cursor.fetchall():
        topic = row[0] or "General"
        if topic not in topic_by_device:
            topic_by_device[topic] = {}
        topic_by_device[topic][row[1]] = row[2]

    # Average response time by topic
    cursor.execute("""
        SELECT topic, AVG(response_time_ms)
        FROM chat_logs
        GROUP BY topic
    """)
    avg_response_by_topic = {r[0] or "General": round(r[1]) for r in cursor.fetchall()}

    conn.close()

    return {
        "topics": topic_distribution,
        "topic_distribution": topic_distribution,
        "topic_by_device": topic_by_device,
        "avg_response_time_by_topic": avg_response_by_topic
    }

@app.get("/api/analytics/time-patterns")
async def get_time_patterns(username: str = Depends(verify_admin)):
    """Get hourly and daily usage patterns."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    # Hourly distribution
    cursor.execute("""
        SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, COUNT(*)
        FROM chat_logs
        GROUP BY hour
        ORDER BY hour
    """)
    hourly = [{"hour": r[0], "count": r[1]} for r in cursor.fetchall()]

    # Day of week distribution
    cursor.execute("""
        SELECT CAST(strftime('%w', timestamp) AS INTEGER) as day, COUNT(*)
        FROM chat_logs
        GROUP BY day
        ORDER BY day
    """)
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    daily = [{"day": day_names[r[0]], "count": r[1]} for r in cursor.fetchall()]

    # Last 30 days
    cursor.execute("""
        SELECT DATE(timestamp), COUNT(*)
        FROM chat_logs
        WHERE timestamp >= datetime('now', '-30 days')
        GROUP BY DATE(timestamp)
        ORDER BY DATE(timestamp)
    """)
    last_30_days = [{"date": r[0], "count": r[1]} for r in cursor.fetchall()]

    # Visitor stats (new vs return)
    cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE is_return_visitor = 0")
    new_visitors = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE is_return_visitor = 1")
    return_visitors = cursor.fetchone()[0] or 0

    conn.close()

    return {
        "hourly": hourly,
        "daily": daily,
        "hourly_distribution": hourly,
        "daily_distribution": daily,
        "last_30_days": last_30_days,
        "visitor_stats": {
            "new_visitors": new_visitors,
            "returning_visitors": return_visitors
        }
    }

@app.get("/api/analytics/terms")
async def get_common_terms(username: str = Depends(verify_admin)):
    """Get most common words in user queries."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    cursor.execute("SELECT user_query FROM chat_logs")
    queries = cursor.fetchall()

    # Simple word frequency analysis
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
                  "of", "with", "is", "are", "was", "were", "be", "been", "being",
                  "what", "when", "where", "who", "why", "how", "i", "you", "we", "they"}

    word_freq = Counter()
    for query in queries:
        if query[0]:
            words = re.findall(r'\b[a-z]{3,}\b', query[0].lower())
            words = [w for w in words if w not in stop_words]
            word_freq.update(words)

    most_common = [{"term": word, "count": count}
                   for word, count in word_freq.most_common(50)]

    # Common phrases (bigrams)
    bigram_freq = Counter()
    for query in queries:
        if query[0]:
            words = re.findall(r'\b[a-z]+\b', query[0].lower())
            words = [w for w in words if w not in stop_words]
            for i in range(len(words) - 1):
                bigram = f"{words[i]} {words[i+1]}"
                bigram_freq[bigram] += 1

    common_phrases = [{"phrase": phrase, "count": count}
                     for phrase, count in bigram_freq.most_common(30)]

    conn.close()

    return {
        "terms": most_common,
        "most_common_terms": most_common,
        "common_phrases": common_phrases
    }

@app.get("/api/analytics/low-confidence")
async def get_low_confidence_queries(username: str = Depends(verify_admin)):
    """Get queries with low RAG similarity scores."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    # Get queries with low similarity scores (higher score = less similar in ChromaDB)
    cursor.execute("""
        SELECT timestamp, user_query, avg_similarity_score
        FROM chat_logs
        WHERE avg_similarity_score IS NOT NULL
        ORDER BY avg_similarity_score DESC
        LIMIT 20
    """)
    low_confidence = [{
        "timestamp": r[0],
        "query": r[1],
        "rag_score": r[2]
    } for r in cursor.fetchall()]

    conn.close()

    return {"queries": low_confidence}

@app.get("/api/analytics/costs")
async def get_cost_analytics(username: str = Depends(verify_admin)):
    """Get token usage and cost analytics."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    # Overall costs
    cursor.execute("""
        SELECT SUM(input_tokens), SUM(output_tokens), SUM(estimated_cost), COUNT(*)
        FROM chat_logs
        WHERE cached = 0
    """)
    overall = cursor.fetchone()
    total_input = overall[0] or 0
    total_output = overall[1] or 0
    total_cost = overall[2] or 0
    api_calls = overall[3] or 0

    # Daily costs (last 30 days)
    cursor.execute("""
        SELECT DATE(timestamp), SUM(input_tokens), SUM(output_tokens), SUM(estimated_cost)
        FROM chat_logs
        WHERE timestamp >= datetime('now', '-30 days') AND cached = 0
        GROUP BY DATE(timestamp)
        ORDER BY DATE(timestamp)
    """)
    daily_costs = [{
        "date": r[0],
        "input_tokens": r[1] or 0,
        "output_tokens": r[2] or 0,
        "cost": round(r[3] or 0, 4)
    } for r in cursor.fetchall()]

    # Cost by topic
    cursor.execute("""
        SELECT topic, SUM(input_tokens), SUM(output_tokens), SUM(estimated_cost), COUNT(*)
        FROM chat_logs
        WHERE cached = 0
        GROUP BY topic
        ORDER BY SUM(estimated_cost) DESC
    """)
    cost_by_topic = [{
        "topic": r[0] or "General",
        "input_tokens": r[1] or 0,
        "output_tokens": r[2] or 0,
        "cost": round(r[3] or 0, 4),
        "queries": r[4]
    } for r in cursor.fetchall()]

    # Cached responses count
    cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE cached = 1")
    cached_count = cursor.fetchone()[0]

    # Today's cost
    cursor.execute("""
        SELECT SUM(estimated_cost) FROM chat_logs
        WHERE DATE(timestamp) = DATE('now') AND cached = 0
    """)
    today_cost = cursor.fetchone()[0] or 0

    # Average messages per session
    cursor.execute("""
        SELECT AVG(msg_count) FROM (
            SELECT session_id, COUNT(*) as msg_count
            FROM chat_logs
            GROUP BY session_id
        )
    """)
    avg_messages = cursor.fetchone()[0] or 0

    conn.close()

    return {
        "model": "claude-3-haiku-20240307",
        "model_display": "Claude 3 Haiku",
        "input_cost_per_mtok": HAIKU_INPUT_COST_PER_MTOK,
        "output_cost_per_mtok": HAIKU_OUTPUT_COST_PER_MTOK,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost": round(total_cost, 4),
        "total_cost_usd": round(total_cost, 4),
        "api_calls": api_calls,
        "cached_responses": cached_count,
        "cache_hit_rate": round((cached_count / (api_calls + cached_count) * 100)
                               if (api_calls + cached_count) > 0 else 0, 2),
        "avg_input_tokens_per_call": round(total_input / api_calls) if api_calls > 0 else 0,
        "avg_output_tokens_per_call": round(total_output / api_calls) if api_calls > 0 else 0,
        "avg_cost_per_call": round(total_cost / api_calls, 4) if api_calls > 0 else 0,
        "avg_cost_per_chat": round(total_cost / api_calls, 4) if api_calls > 0 else 0,
        "today_cost": round(today_cost, 4),
        "avg_messages_per_session": round(avg_messages, 1),
        "daily_costs": daily_costs,
        "cost_by_topic": cost_by_topic
    }

@app.get("/api/analytics/advanced")
async def get_advanced_analytics(username: str = Depends(verify_admin)):
    """Get advanced user analytics data."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    # Screen resolutions distribution
    cursor.execute("""
        SELECT screen_width || 'x' || screen_height as resolution, COUNT(*) as count
        FROM chat_logs
        WHERE screen_width IS NOT NULL AND screen_height IS NOT NULL
        GROUP BY resolution
        ORDER BY count DESC
        LIMIT 10
    """)
    screen_resolutions = [{"resolution": r[0], "count": r[1]} for r in cursor.fetchall()]

    # Language distribution
    cursor.execute("""
        SELECT language, COUNT(*) as count
        FROM chat_logs
        WHERE language IS NOT NULL AND language != ''
        GROUP BY language
        ORDER BY count DESC
        LIMIT 10
    """)
    languages = [{"language": r[0], "count": r[1]} for r in cursor.fetchall()]

    # Connection types
    cursor.execute("""
        SELECT connection_type, COUNT(*) as count
        FROM chat_logs
        WHERE connection_type IS NOT NULL
        GROUP BY connection_type
        ORDER BY count DESC
    """)
    connection_types = [{"type": r[0], "count": r[1]} for r in cursor.fetchall()]

    # Color scheme preference
    cursor.execute("""
        SELECT color_scheme, COUNT(*) as count
        FROM chat_logs
        WHERE color_scheme IS NOT NULL
        GROUP BY color_scheme
    """)
    color_schemes = [{"scheme": r[0], "count": r[1]} for r in cursor.fetchall()]

    # Input type (touch vs mouse)
    cursor.execute("""
        SELECT input_type, COUNT(*) as count
        FROM chat_logs
        WHERE input_type IS NOT NULL
        GROUP BY input_type
    """)
    input_types = [{"type": r[0], "count": r[1]} for r in cursor.fetchall()]

    # Average session duration
    cursor.execute("""
        SELECT AVG(session_duration_ms) / 1000 as avg_seconds
        FROM chat_logs
        WHERE session_duration_ms IS NOT NULL
    """)
    avg_session_duration = cursor.fetchone()[0] or 0

    # Average time between messages
    cursor.execute("""
        SELECT AVG(time_since_last_msg_ms) / 1000 as avg_seconds
        FROM chat_logs
        WHERE time_since_last_msg_ms IS NOT NULL
    """)
    avg_time_between_msgs = cursor.fetchone()[0] or 0

    # ISP distribution
    cursor.execute("""
        SELECT isp, COUNT(*) as count
        FROM chat_logs
        WHERE isp IS NOT NULL AND isp != ''
        GROUP BY isp
        ORDER BY count DESC
        LIMIT 10
    """)
    isps = [{"isp": r[0], "count": r[1]} for r in cursor.fetchall()]

    # Device models (top 10)
    cursor.execute("""
        SELECT device_brand || ' ' || device_model as device, COUNT(*) as count
        FROM chat_logs
        WHERE device_brand != 'Unknown'
        GROUP BY device
        ORDER BY count DESC
        LIMIT 10
    """)
    device_models = [{"device": r[0], "count": r[1]} for r in cursor.fetchall()]

    # Referrer sources
    cursor.execute("""
        SELECT referrer, COUNT(*) as count
        FROM chat_logs
        WHERE referrer IS NOT NULL AND referrer != ''
        GROUP BY referrer
        ORDER BY count DESC
        LIMIT 10
    """)
    referrers = [{"source": r[0], "count": r[1]} for r in cursor.fetchall()]

    # Browser versions (top 10)
    cursor.execute("""
        SELECT browser || ' ' || browser_version as browser_full, COUNT(*) as count
        FROM chat_logs
        WHERE browser IS NOT NULL
        GROUP BY browser_full
        ORDER BY count DESC
        LIMIT 10
    """)
    browsers = [{"browser": r[0], "count": r[1]} for r in cursor.fetchall()]

    # OS versions (top 10)
    cursor.execute("""
        SELECT os || ' ' || os_version as os_full, COUNT(*) as count
        FROM chat_logs
        WHERE os IS NOT NULL
        GROUP BY os_full
        ORDER BY count DESC
        LIMIT 10
    """)
    operating_systems = [{"os": r[0], "count": r[1]} for r in cursor.fetchall()]

    # Geographic data with coordinates for map
    cursor.execute("""
        SELECT city, region_name, country, latitude, longitude, COUNT(*) as count
        FROM chat_logs
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY city, country
        ORDER BY count DESC
        LIMIT 50
    """)
    geo_data = [{"city": r[0], "region": r[1], "country": r[2],
                 "lat": r[3], "lng": r[4], "count": r[5]} for r in cursor.fetchall()]

    conn.close()

    return {
        "screen_resolutions": screen_resolutions,
        "languages": languages,
        "connection_types": connection_types,
        "color_schemes": color_schemes,
        "input_types": input_types,
        "avg_session_duration_seconds": round(avg_session_duration, 1),
        "avg_time_between_msgs_seconds": round(avg_time_between_msgs, 1),
        "isps": isps,
        "device_models": device_models,
        "referrers": referrers,
        "browsers": browsers,
        "operating_systems": operating_systems,
        "geo_data": geo_data
    }


@app.get("/api/analytics/users")
async def get_individual_users(page: int = 1, per_page: int = 50, username: str = Depends(verify_admin)):
    """Get individual user profiles with all their data."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    # Count unique users (by session_id or IP)
    cursor.execute("""
        SELECT COUNT(DISTINCT COALESCE(session_id, ip_address)) FROM chat_logs
    """)
    total_users = cursor.fetchone()[0]

    # Get unique users with their most recent data and aggregates
    cursor.execute("""
        SELECT
            COALESCE(session_id, ip_address) as user_id,
            MAX(ip_address) as ip,
            MAX(country) as country,
            MAX(city) as city,
            MAX(region_name) as region,
            MAX(latitude) as lat,
            MAX(longitude) as lng,
            MAX(timezone) as timezone,
            MAX(isp) as isp,
            MAX(device_type) as device_type,
            MAX(device_brand) as device_brand,
            MAX(device_model) as device_model,
            MAX(browser) as browser,
            MAX(browser_version) as browser_version,
            MAX(os) as os,
            MAX(os_version) as os_version,
            MAX(screen_width) as screen_width,
            MAX(screen_height) as screen_height,
            MAX(language) as language,
            MAX(connection_type) as connection_type,
            MAX(color_scheme) as color_scheme,
            MAX(input_type) as input_type,
            MAX(referrer) as referrer,
            COUNT(*) as message_count,
            MIN(timestamp) as first_seen,
            MAX(timestamp) as last_seen,
            MAX(session_duration_ms) as session_duration_ms,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(estimated_cost) as total_cost,
            MAX(is_return_visitor) as is_return_visitor
        FROM chat_logs
        GROUP BY user_id
        ORDER BY last_seen DESC
        LIMIT ? OFFSET ?
    """, (per_page, (page - 1) * per_page))

    users = []
    for row in cursor.fetchall():
        users.append({
            "user_id": row[0][:16] + "..." if row[0] and len(row[0]) > 16 else row[0],
            "user_id_full": row[0],
            "ip": row[1],
            "location": {
                "country": row[2],
                "city": row[3],
                "region": row[4],
                "lat": row[5],
                "lng": row[6],
                "timezone": row[7]
            },
            "isp": row[8],
            "device": {
                "type": row[9],
                "brand": row[10],
                "model": row[11]
            },
            "browser": {
                "name": row[12],
                "version": row[13]
            },
            "os": {
                "name": row[14],
                "version": row[15]
            },
            "screen": f"{row[16]}x{row[17]}" if row[16] and row[17] else None,
            "language": row[18],
            "connection": row[19],
            "color_scheme": row[20],
            "input_type": row[21],
            "referrer": row[22],
            "stats": {
                "message_count": row[23],
                "first_seen": row[24],
                "last_seen": row[25],
                "session_duration_ms": row[26],
                "total_tokens": (row[27] or 0) + (row[28] or 0),
                "total_cost": round(row[29], 6) if row[29] else 0
            },
            "is_return_visitor": bool(row[30])
        })

    conn.close()

    total_pages = (total_users + per_page - 1) // per_page

    return {
        "users": users,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total_users,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages
        }
    }


@app.get("/api/analytics/user/{user_id}/chats")
async def get_user_chats(user_id: str, username: str = Depends(verify_admin)):
    """Get all chats for a specific user."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, timestamp, user_query, ai_response, response_time_ms, topic, feedback_given,
               avg_similarity_score, input_tokens, output_tokens, estimated_cost, session_id
        FROM chat_logs
        WHERE session_id = ? OR ip_address = ?
        ORDER BY timestamp ASC
        LIMIT 100
    """, (user_id, user_id))

    chats = [{
        "id": r[0],
        "timestamp": r[1],
        "query": r[2],
        "response": r[3],
        "response_time_ms": r[4],
        "topic": r[5],
        "feedback": r[6],
        "confidence": round(r[7], 3) if r[7] else None,
        "tokens": (r[8] or 0) + (r[9] or 0),
        "cost": round(r[10], 6) if r[10] else None,
        "session_id": r[11]
    } for r in cursor.fetchall()]

    conn.close()
    return {"chats": chats}



@app.get("/api/analytics/conversations")
async def get_conversations(page: int = 1, per_page: int = 10, username: str = Depends(verify_admin)):
    """Get all conversations grouped by session."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()
    
    # Get unique sessions with basic info
    cursor.execute("""
        SELECT session_id, 
               MIN(timestamp) as first_msg,
               MAX(timestamp) as last_msg,
               COUNT(*) as msg_count,
               city, country, device_type
        FROM chat_logs 
        WHERE session_id IS NOT NULL AND session_id != ''
        GROUP BY session_id
        ORDER BY MAX(timestamp) DESC
        LIMIT ? OFFSET ?
    """, (per_page, (page - 1) * per_page))
    
    sessions = cursor.fetchall()
    
    # Get total count for pagination
    cursor.execute("SELECT COUNT(DISTINCT session_id) FROM chat_logs WHERE session_id IS NOT NULL AND session_id != ''")
    total = cursor.fetchone()[0]
    
    conversations = []
    for session in sessions:
        session_id, first_msg, last_msg, msg_count, city, country, device = session
        
        # Get all messages for this session
        cursor.execute("""
            SELECT id, timestamp, user_query, ai_response, response_time_ms, topic, feedback_given
            FROM chat_logs
            WHERE session_id = ?
            ORDER BY timestamp ASC
        """, (session_id,))
        
        messages = [{
            "id": r[0],
            "timestamp": r[1],
            "query": r[2],
            "response": r[3],
            "response_time_ms": r[4],
            "topic": r[5],
            "feedback": r[6]
        } for r in cursor.fetchall()]
        
        location = f"{city}, {country}" if city and country else (city or country or "Unknown")
        
        conversations.append({
            "session_id": session_id,
            "first_message": first_msg,
            "last_message": last_msg,
            "message_count": msg_count,
            "location": location,
            "device": device or "Unknown",
            "messages": messages
        })
    
    conn.close()
    
    return {
        "conversations": conversations,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
            "has_next": page < (total + per_page - 1) // per_page
        }
    }

@app.get("/api/analytics/queries")
async def get_all_queries(page: int = 1, per_page: int = 20, username: str = Depends(verify_admin)):
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chat_logs")
    total = cursor.fetchone()[0]
    cursor.execute("""SELECT id, timestamp, user_query, ai_response, response_time_ms, ip_address,
                     country, region_name, city, timezone, device_type, device_brand, device_model,
                     browser, browser_version, os, os_version, isp, topic, feedback_given,
                     messages_in_session, is_return_visitor, referrer, avg_similarity_score,
                     input_tokens, output_tokens, estimated_cost, session_id
                     FROM chat_logs ORDER BY id DESC LIMIT ? OFFSET ?""",
                  (per_page, (page-1)*per_page))
    queries = [{
        "id": r[0], "timestamp": r[1], "query": r[2], "response": r[3],
        "response_time_ms": r[4], "ip": r[5], "country": r[6], "region": r[7],
        "city": r[8], "timezone": r[9], "device_type": r[10], "device_brand": r[11],
        "device_model": r[12], "browser": r[13], "browser_version": r[14], "os": r[15],
        "os_version": r[16], "isp": r[17], "topic": r[18], "feedback_given": r[19],
        "messages_in_session": r[20], "is_return_visitor": r[21], "referrer": r[22],
        "avg_similarity_score": round(r[23], 3) if r[23] else None,
        "input_tokens": r[24], "output_tokens": r[25],
        "session_id": r[27] if len(r) > 27 else None,
        "estimated_cost": round(r[26], 6) if r[26] else None
    } for r in cursor.fetchall()]
    conn.close()
    return {
        "queries": queries,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total+per_page-1)//per_page,
            "has_next": page < (total+per_page-1)//per_page,
            "has_prev": page > 1
        }
    }

app.mount("/static", StaticFiles(directory="/app/frontend"), name="static")

@app.get("/admin")
async def serve_admin(username: str = Depends(verify_admin)):
    return FileResponse("/app/frontend/admin.html")

@app.get("/")
async def serve_frontend():
    return FileResponse("/app/frontend/index.html")


@app.get("/api/backup/download")
async def download_backup(username: str = Depends(verify_admin)):
    """Download a zip backup of the database and vector store."""
    import zipfile
    import tempfile

    # Create a temporary zip file
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    zip_filename = f"faith-companion-backup_{timestamp}.zip"
    
    # Create temp file
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, zip_filename)
    
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add analytics database
            db_path = "/app/data/analytics.db"
            if os.path.exists(db_path):
                zipf.write(db_path, "analytics.db")
            
            # Add chroma_db folder
            chroma_path = "/app/data/chroma_db"
            if os.path.exists(chroma_path):
                for root, dirs, files in os.walk(chroma_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join("chroma_db", os.path.relpath(file_path, chroma_path))
                        zipf.write(file_path, arcname)
        
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=zip_filename,
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


# ============== FEEDBACK ANALYTICS ==============

@app.get("/api/analytics/feedback/list")
async def get_feedback_list(page: int = 1, per_page: int = 20, feedback_type: str = None, username: str = Depends(verify_admin)):
    """Get paginated list of feedback with comments."""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        where_clause = ""
        params = []
        if feedback_type and feedback_type in ['positive', 'negative']:
            where_clause = "WHERE f.feedback_type = ?"
            params.append(feedback_type)

        cursor.execute(f"SELECT COUNT(*) as total FROM feedback f {where_clause}", params)
        total = cursor.fetchone()['total']

        offset = (page - 1) * per_page
        cursor.execute(f"""
            SELECT
                f.id, f.chat_log_id, f.feedback_type, f.comment, f.timestamp,
                c.user_query, c.ai_response, c.topic, c.city, c.country
            FROM feedback f
            LEFT JOIN chat_logs c ON f.chat_log_id = c.id
            {where_clause}
            ORDER BY f.timestamp DESC
            LIMIT ? OFFSET ?
        """, params + [per_page, offset])

        feedback_list = []
        for row in cursor.fetchall():
            ai_resp = row['ai_response'] or ''
            feedback_list.append({
                "id": row['id'],
                "chat_log_id": row['chat_log_id'],
                "feedback_type": row['feedback_type'],
                "comment": row['comment'],
                "timestamp": row['timestamp'],
                "user_query": row['user_query'],
                "ai_response": ai_resp[:300] + '...' if len(ai_resp) > 300 else ai_resp,
                "topic": row['topic'],
                "location": f"{row['city']}, {row['country']}" if row['city'] else row['country']
            })

        conn.close()
        total_pages = (total + per_page - 1) // per_page

        return {
            "feedback": feedback_list,
            "pagination": {
                "page": page, "per_page": per_page, "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    except Exception as e:
        logger.error(f"Error getting feedback list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/feedback/export")
async def export_feedback_csv(feedback_type: str = None, username: str = Depends(verify_admin)):
    """Export feedback data as CSV."""
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        where_clause = ""
        params = []
        if feedback_type and feedback_type in ['positive', 'negative']:
            where_clause = "WHERE f.feedback_type = ?"
            params.append(feedback_type)

        cursor.execute(f"""
            SELECT
                f.id, f.feedback_type, f.comment, f.timestamp,
                c.user_query, c.ai_response, c.topic, c.city, c.country
            FROM feedback f
            LEFT JOIN chat_logs c ON f.chat_log_id = c.id
            {where_clause}
            ORDER BY f.timestamp DESC
        """, params)

        rows = cursor.fetchall()
        conn.close()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Feedback Type', 'Comment', 'Timestamp', 'User Query', 'AI Response', 'Topic', 'Location'])

        for row in rows:
            location = f"{row['city']}, {row['country']}" if row['city'] else (row['country'] or '')
            writer.writerow([
                row['id'], row['feedback_type'], row['comment'] or '',
                row['timestamp'], row['user_query'] or '', row['ai_response'] or '',
                row['topic'] or '', location
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=feedback_export.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============== PRIEST ADMIN AUTH ==============
PRIEST_ADMIN_USERNAME = os.environ.get("PRIEST_ADMIN_USERNAME", "priestadmin")
PRIEST_ADMIN_PASSWORD = os.environ.get("PRIEST_ADMIN_PASSWORD")
if not PRIEST_ADMIN_PASSWORD:
    raise RuntimeError("PRIEST_ADMIN_PASSWORD environment variable must be set")

def verify_priest_admin(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()
    
    # Check rate limit (shared with admin)
    allowed, reset_time = check_admin_rate_limit(ip)
    if not allowed:
        logger.warning(f"Priest admin login rate limited for IP {ip}. Reset in {reset_time}s")
        raise HTTPException(status_code=429, detail=f"Too many login attempts. Try again in {reset_time // 60} minutes.", headers={"Retry-After": str(reset_time)})
    
    if not (secrets.compare_digest(credentials.username.encode(), PRIEST_ADMIN_USERNAME.encode()) and 
            secrets.compare_digest(credentials.password.encode(), PRIEST_ADMIN_PASSWORD.encode())):
        record_failed_admin_login(ip)
        raise HTTPException(status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Basic"})
    
    clear_admin_login_attempts(ip)
    return credentials.username

# ============== PRIEST ADMIN ENDPOINTS ==============

@app.get("/api/phadmin/overview")
async def get_priest_overview(username: str = Depends(verify_priest_admin)):
    """Get ministry impact overview for priest admin (no sensitive data)."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM chat_logs")
    total_chats = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT session_id) FROM chat_logs")
    unique_visitors = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM feedback WHERE feedback_type = 'positive'")
    positive = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM feedback WHERE feedback_type = 'negative'")
    negative = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE is_return_visitor = 1")
    return_visitors = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(messages_in_session) FROM chat_logs")
    avg_depth = cursor.fetchone()[0] or 0
    
    conn.close()
    
    total_feedback = positive + negative
    satisfaction_rate = round((positive / total_feedback * 100) if total_feedback > 0 else 0, 2)
    return_rate = round((return_visitors / total_chats * 100) if total_chats > 0 else 0, 2)
    
    return {
        "total_conversations": total_chats,
        "unique_visitors": unique_visitors,
        "satisfaction_rate": satisfaction_rate,
        "positive_feedback": positive,
        "negative_feedback": negative,
        "return_visitors": return_visitors,
        "return_visitor_rate": return_rate,
        "avg_session_depth": round(avg_depth, 2)
    }

@app.get("/api/phadmin/spiritual-direction")
async def get_priest_spiritual_direction(username: str = Depends(verify_priest_admin)):
    """Get spiritual direction requests for priest admin (read-only)."""
    conn = sqlite3.connect(ANALYTICS_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM spiritual_direction_requests ORDER BY timestamp DESC")
    requests = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"requests": requests}

@app.get("/api/phadmin/spiritual-direction/export")
async def export_priest_spiritual_direction(username: str = Depends(verify_priest_admin)):
    """Export spiritual direction requests as CSV for priest admin."""
    conn = sqlite3.connect(ANALYTICS_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, timestamp, name, phone, email, request_type, message, status FROM spiritual_direction_requests ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Date', 'Name', 'Phone', 'Email', 'Request Type', 'Message', 'Status'])
    for row in rows:
        writer.writerow([row['id'], row['timestamp'], row['name'], row['phone'], row['email'] or '', row['request_type'], row['message'] or '', row['status']])
    
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=spiritual_direction_requests.csv"})

@app.get("/api/phadmin/topics")
async def get_priest_topics(username: str = Depends(verify_priest_admin)):
    """Get topic distribution for priest admin."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT topic, COUNT(*) as count FROM chat_logs GROUP BY topic ORDER BY count DESC")
    topics = [{"topic": r[0] or "General", "count": r[1]} for r in cursor.fetchall()]
    conn.close()
    return {"topics": topics}

@app.get("/api/phadmin/terms")
async def get_priest_terms(username: str = Depends(verify_priest_admin)):
    """Get common terms/questions for priest admin."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT user_query FROM chat_logs")
    queries = cursor.fetchall()
    conn.close()
    
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "is", "are", "was", "were", "be", "been", "being", "what", "when", "where", "who", "why", "how", "i", "you", "we", "they"}
    word_freq = Counter()
    for query in queries:
        if query[0]:
            words = re.findall(r'\b[a-z]{3,}\b', query[0].lower())
            words = [w for w in words if w not in stop_words]
            word_freq.update(words)
    
    terms = [{"term": word, "count": count} for word, count in word_freq.most_common(30)]
    return {"terms": terms}

@app.get("/api/phadmin/locations")
async def get_priest_locations(username: str = Depends(verify_priest_admin)):
    """Get geographic summary for priest admin (city-level only, no IPs)."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT city, country, COUNT(*) as count FROM chat_logs WHERE city != '' GROUP BY city, country ORDER BY count DESC LIMIT 20")
    locations = [{"city": r[0], "country": r[1], "count": r[2]} for r in cursor.fetchall()]
    conn.close()
    return {"locations": locations}

@app.get("/api/phadmin/time-patterns")
async def get_priest_time_patterns(username: str = Depends(verify_priest_admin)):
    """Get time patterns for priest admin."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, COUNT(*) FROM chat_logs GROUP BY hour ORDER BY hour")
    hourly = [{"hour": r[0], "count": r[1]} for r in cursor.fetchall()]
    
    cursor.execute("SELECT CAST(strftime('%w', timestamp) AS INTEGER) as day, COUNT(*) FROM chat_logs GROUP BY day ORDER BY day")
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    daily = [{"day": day_names[r[0]], "count": r[1]} for r in cursor.fetchall()]
    
    conn.close()
    
    peak_hour = max(hourly, key=lambda x: x['count'])['hour'] if hourly else 0
    peak_day = max(daily, key=lambda x: x['count'])['day'] if daily else "N/A"
    
    return {"hourly": hourly, "daily": daily, "peak_hour": peak_hour, "peak_day": peak_day}

@app.get("/api/phadmin/feedback")
async def get_priest_feedback(username: str = Depends(verify_priest_admin)):
    """Get recent feedback for priest admin (anonymized)."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM feedback WHERE feedback_type = 'positive'")
    positive = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM feedback WHERE feedback_type = 'negative'")
    negative = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT f.feedback_type, f.comment, f.timestamp, c.topic
        FROM feedback f
        JOIN chat_logs c ON f.chat_log_id = c.id
        WHERE f.comment IS NOT NULL AND f.comment != ''
        ORDER BY f.timestamp DESC
        LIMIT 20
    """)
    comments = [{"type": r[0], "comment": r[1], "date": r[2][:10], "topic": r[3]} for r in cursor.fetchall()]
    
    conn.close()
    return {"positive": positive, "negative": negative, "comments": comments}

@app.get("/api/phadmin/sample-questions")
async def get_priest_sample_questions(username: str = Depends(verify_priest_admin)):
    """Get anonymized sample questions for pastoral insight."""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, user_query, topic
        FROM chat_logs
        WHERE user_query IS NOT NULL AND LENGTH(user_query) > 10
        ORDER BY timestamp DESC
        LIMIT 50
    """)
    questions = [{"date": r[0][:10], "question": r[1], "topic": r[2] or "General"} for r in cursor.fetchall()]
    conn.close()
    return {"questions": questions}

@app.get("/phadmin")
async def serve_priest_admin(username: str = Depends(verify_priest_admin)):
    return FileResponse("/app/frontend/phadmin.html")

# ============== SECURITY HEADERS MIDDLEWARE ==============
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # CSP allowing Chart.js from CDN
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'"
    return response

# ============== ADMIN LOGIN RATE LIMITING ==============
admin_login_attempts: Dict[str, List[float]] = defaultdict(list)
ADMIN_RATE_LIMIT_ATTEMPTS = 10  # Max attempts
ADMIN_RATE_LIMIT_WINDOW = 300  # 15 minutes in seconds
ADMIN_LOCKOUT_DURATION = 300  # 30 minutes lockout after exceeded

def check_admin_rate_limit(ip_address: str) -> tuple[bool, int]:
    """Check if IP is rate limited for admin login. Returns (allowed, seconds_until_reset)."""
    now = time_module.time()
    window_start = now - ADMIN_RATE_LIMIT_WINDOW
    
    # Clean old attempts
    admin_login_attempts[ip_address] = [t for t in admin_login_attempts[ip_address] if t > window_start]
    
    attempts = len(admin_login_attempts[ip_address])
    
    if attempts >= ADMIN_RATE_LIMIT_ATTEMPTS:
        oldest = min(admin_login_attempts[ip_address])
        reset_time = int(oldest + ADMIN_LOCKOUT_DURATION - now)
        return False, max(0, reset_time)
    
    return True, 0

def record_failed_admin_login(ip_address: str):
    """Record a failed admin login attempt."""
    admin_login_attempts[ip_address].append(time_module.time())
    logger.warning(f"Failed admin login attempt from {ip_address}. Total attempts: {len(admin_login_attempts[ip_address])}")

def clear_admin_login_attempts(ip_address: str):
    """Clear login attempts after successful login."""
    if ip_address in admin_login_attempts:
        del admin_login_attempts[ip_address]

# ============== LOGOUT ENDPOINTS ==============
@app.get("/admin/logout")
async def admin_logout():
    """Force browser to clear cached admin credentials."""
    raise HTTPException(
        status_code=401,
        detail="Logged out successfully. Close this tab or click Cancel to return to login.",
        headers={"WWW-Authenticate": "Basic realm=\"Admin Logout\""}
    )

@app.get("/phadmin/logout")
async def priest_admin_logout():
    """Force browser to clear cached priest admin credentials."""
    raise HTTPException(
        status_code=401,
        detail="Logged out successfully. Close this tab or click Cancel to return to login.",
        headers={"WWW-Authenticate": "Basic realm=\"Priest Admin Logout\""}
    )

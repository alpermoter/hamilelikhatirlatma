"""
Hamilelik Hatirlatma Otomasyonu
================================
- Saat 9:00 - 23:59 arasi her saat basi SU icme hatirlatmasi
- Her gun saat 21:00 TANSIYON olcum hatirlatmasi
- Cevap gelmezse 5 dakika sonra tekrar hatirlatir
- "ertele" -> 1 saat sonraya oteler
- "X saat ertele" -> X saat sonraya oteler
- "ictim" / "olctum" / "120/80" gibi cevaplarda hatirlatma kapatilir
"""

import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Europe/Istanbul")
WATER_START_HOUR = 9
WATER_END_HOUR = 23
BP_HOUR = 21
BP_MINUTE = 0
REPEAT_AFTER_MINUTES = 5
DEFAULT_SNOOZE_HOURS = 1

GREEN_API_INSTANCE = os.environ.get("GREEN_API_INSTANCE", "").strip()
GREEN_API_TOKEN = os.environ.get("GREEN_API_TOKEN", "").strip()
TARGET_PHONE = os.environ.get("TARGET_PHONE", "").strip()
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

STATE_FILE = Path(__file__).parent / "state.json"


def now_tr():
    return datetime.now(TZ)


def iso(dt):
    return dt.isoformat() if dt else None


def parse_iso(s):
    if not s:
        return None
    return datetime.fromisoformat(s)


def normalize(text):
    if not text:
        return ""
    tr_map = {
        "İ": "i", "I": "i", "Ç": "c", "Ş": "s",
        "Ğ": "g", "Ü": "u", "Ö": "o",
        "ı": "i", "ç": "c", "ş": "s",
        "ğ": "g", "ü": "u", "ö": "o",
    }
    for k, v in tr_map.items():
        text = text.replace(k, v)
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s/\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def green_url(method):
    return "https://api.green-api.com/waInstance" + GREEN_API_INSTANCE + "/" + method + "/" + GREEN_API_TOKEN


def send_whatsapp(message):
    if DRY_RUN:
        print("[DRY_RUN] " + message)
        return True
    if not (GREEN_API_INSTANCE and GREEN_API_TOKEN and TARGET_PHONE):
        print("HATA: Green-API ayarlari veya hedef numara eksik!")
        return False
    chat_id = TARGET_PHONE + "@c.us"
    try:
        r = requests.post(
            green_url("sendMessage"),
            json={"chatId": chat_id, "message": message},
            timeout=15,
        )
        r.raise_for_status()
        print("[OK] Mesaj gonderildi: " + message[:60])
        return True
    except Exception as e:
        print("[HATA] Mesaj gonderilemedi: " + str(e))
        return False


def fetch_incoming_messages():
    messages = []
    if DRY_RUN or not (GREEN_API_INSTANCE and GREEN_API_TOKEN):
        return messages
    for _ in range(50):
        try:
            r = requests.get(green_url("receiveNotification"), timeout=15)
            if r.status_code == 200 and r.text and r.text != "null":
                data = r.json()
                if not data:
                    break
                receipt_id = data.get("receiptId")
                body = data.get("body", {})
                if body.get("typeWebhook") == "incomingMessageReceived":
                    sender = body.get("senderData", {}).get("sender", "")
                    msg_data = body.get("messageData", {})
                    text = ""
                    if msg_data.get("typeMessage") == "textMessage":
                        text = msg_data.get("textMessageData", {}).get("textMessage", "")
                    elif msg_data.get("typeMessage") == "extendedTextMessage":
                        text = msg_data.get("extendedTextMessageData", {}).get("text", "")
                    ts = body.get("timestamp", 0)
                    if sender.startswith(TARGET_PHONE) and text:
                        messages.append({
                            "text": text,
                            "timestamp": ts,
                            "received_at": datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(TZ),
                        })
                if receipt_id:
                    requests.delete(green_url("deleteNotification/" + str(receipt_id)), timeout=15)
            else:
                break
        except Exception as e:
            print("[HATA] Mesaj okuma: " + str(e))
            break
    return messages


WATER_OK_KEYWORDS = [
    "ictim", "icdim", "tamam", "ok", "okey", "evet",
    "yaptim", "done", "icildi", "bitti",
]
BP_OK_KEYWORDS = ["olctum", "olculdu", "yaptim", "tansiyon", "olcum"]
BP_NUMERIC_PATTERN = re.compile(r"\b(\d{2,3})\s*[/\-]\s*(\d{2,3})\b")
SNOOZE_HOUR_PATTERN = re.compile(r"(\d+)\s*saat\s*(ertele|sonra)")
SNOOZE_MIN_PATTERN = re.compile(r"(\d+)\s*(dakika|dk|min)\s*(ertele|sonra)")
ERTELE_KEYWORD = re.compile(r"\bertele\b")


def classify_message(text):
    norm = normalize(text)
    m = SNOOZE_HOUR_PATTERN.search(norm)
    if m:
        return {"intent": "snooze", "snooze_minutes": int(m.group(1)) * 60}
    m = SNOOZE_MIN_PATTERN.search(norm)
    if m:
        return {"intent": "snooze", "snooze_minutes": int(m.group(1))}
    if ERTELE_KEYWORD.search(norm):
        return {"intent": "snooze", "snooze_minutes": DEFAULT_SNOOZE_HOURS * 60}
    if BP_NUMERIC_PATTERN.search(norm):
        return {"intent": "bp_ok"}
    for kw in BP_OK_KEYWORDS:
        if kw in norm:
            return {"intent": "bp_ok"}
    for kw in WATER_OK_KEYWORDS:
        if kw in norm:
            return {"intent": "water_ok"}
    return {"intent": "unknown"}


DEFAULT_STATE = {
    "water": {
        "slot_date": None, "slot_hour": None, "status": "idle",
        "first_sent_at": None, "last_sent_at": None,
        "snooze_until": None, "send_count": 0,
    },
    "bp": {
        "date": None, "status": "idle",
        "first_sent_at": None, "last_sent_at": None,
        "snooze_until": None, "send_count": 0,
    },
    "last_run_at": None,
}


def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in DEFAULT_STATE.items():
                if k not in data:
                    data[k] = v
                elif isinstance(v, dict):
                    for kk, vv in v.items():
                        if kk not in data[k]:
                            data[k][kk] = vv
            return data
        except Exception as e:
            print("[UYARI] state.json okunamadi: " + str(e))
    return json.loads(json.dumps(DEFAULT_STATE))


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def process_messages(state, messages):
    now = now_tr()
    for msg in messages:
        info = classify_message(msg["text"])
        intent = info["intent"]
        print("[MSG] '" + msg["text"] + "' -> " + str(info))
        if intent == "water_ok":
            if state["water"]["status"] == "pending":
                state["water"]["status"] = "completed"
                state["water"]["snooze_until"] = None
                print("  -> Su tamamlandi")
        elif intent == "bp_ok":
            if state["bp"]["status"] == "pending":
                state["bp"]["status"] = "completed"
                state["bp"]["snooze_until"] = None
                print("  -> Tansiyon tamamlandi")
        elif intent == "snooze":
            mins = info["snooze_minutes"]
            snooze_until = now + timedelta(minutes=mins)
            water_pending = state["water"]["status"] == "pending"
            bp_pending = state["bp"]["status"] == "pending"
            target = None
            if water_pending and bp_pending:
                w_last = parse_iso(state["water"]["last_sent_at"])
                b_last = parse_iso(state["bp"]["last_sent_at"])
                if w_last and b_last:
                    target = "water" if w_last >= b_last else "bp"
                else:
                    target = "water" if w_last else "bp"
            elif water_pending:
                target = "water"
            elif bp_pending:
                target = "bp"
            if target:
                state[target]["snooze_until"] = iso(snooze_until)
                print("  -> " + target + " " + str(mins) + "dk ertelendi")


def get_water_slot(dt):
    if WATER_START_HOUR <= dt.hour <= WATER_END_HOUR:
        return (dt.strftime("%Y-%m-%d"), dt.hour)
    return None


def decide_water(state):
    now = now_tr()
    slot = get_water_slot(now)
    w = state["water"]
    snooze_until = parse_iso(w["snooze_until"])
    if snooze_until and now < snooze_until:
        return None
    if not slot:
        return None
    slot_date, slot_hour = slot
    if w["slot_date"] != slot_date or w["slot_hour"] != slot_hour:
        w["slot_date"] = slot_date
        w["slot_hour"] = slot_hour
        w["status"] = "pending"
        w["first_sent_at"] = iso(now)
        w["last_sent_at"] = iso(now)
        w["snooze_until"] = None
        w["send_count"] = 1
        return (
            "\U0001F4A7 Su zamani! Lutfen bir bardak su ic. "
            "(Saat: " + now.strftime("%H:%M") + ")\n\n"
            "Ictikten sonra 'ictim' yazarsan hatirlatmayi kapatirim. "
            "'Ertele' yazarsan 1 saat oteler, 'X saat ertele' diyebilirsin."
        )
    if w["status"] == "pending":
        last_sent = parse_iso(w["last_sent_at"])
        if last_sent and (now - last_sent) >= timedelta(minutes=REPEAT_AFTER_MINUTES):
            w["last_sent_at"] = iso(now)
            w["send_count"] += 1
            return (
                "\U0001F4A7 Su hatirlatmasi (tekrar #" + str(w["send_count"]) + ") - "
                "hala icmediysen lutfen bir bardak su ic. 'Ictim' yazmayi unutma \U0001F64F"
            )
    return None


def decide_bp(state):
    now = now_tr()
    b = state["bp"]
    today = now.strftime("%Y-%m-%d")
    snooze_until = parse_iso(b["snooze_until"])
    if snooze_until and now < snooze_until:
        return None
    if b["date"] == today and b["status"] == "completed":
        return None
    if b["date"] != today:
        if now.hour < BP_HOUR or (now.hour == BP_HOUR and now.minute < BP_MINUTE):
            return None
        b["date"] = today
        b["status"] = "pending"
        b["first_sent_at"] = iso(now)
        b["last_sent_at"] = iso(now)
        b["snooze_until"] = None
        b["send_count"] = 1
        return (
            "\U0001FA7A Tansiyon olcum zamani! Lutfen tansiyonunu olc.\n\n"
            "Sonucu '120/80' gibi yazabilir veya 'olctum' diyebilirsin. "
            "'Ertele' yazarsan 1 saat oteler."
        )
    if b["status"] == "pending":
        last_sent = parse_iso(b["last_sent_at"])
        if last_sent and (now - last_sent) >= timedelta(minutes=REPEAT_AFTER_MINUTES):
            b["last_sent_at"] = iso(now)
            b["send_count"] += 1
            return (
                "\U0001FA7A Tansiyon hatirlatmasi (tekrar #" + str(b["send_count"]) + ") - "
                "olcum sonucunu paylasmayi unutma. Orn: '115/75'"
            )
    return None


def main():
    now = now_tr()
    print("=== Calisma zamani: " + now.isoformat() + " ===")
    state = load_state()
    messages = fetch_incoming_messages()
    if messages:
        print("[INFO] " + str(len(messages)) + " yeni mesaj alindi")
        process_messages(state, messages)
    water_msg = decide_water(state)
    if water_msg:
        send_whatsapp(water_msg)
    bp_msg = decide_bp(state)
    if bp_msg:
        send_whatsapp(bp_msg)
    state["last_run_at"] = iso(now)
    save_state(state)
    print("[OK] State kaydedildi")
    return 0


if __name__ == "__main__":
    sys.exit(main())

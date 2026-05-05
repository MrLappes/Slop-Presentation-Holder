#!/usr/bin/env python3
"""
Agentic Shield — Automated Presentation with Multi-Personality German TTS

4 Presenters rotating across 14 slides:
  Mike  — Der Ernste (dry humor, professional)
  Nico  — Der Aufgeregte (hyperactive, superlatives)
  Luca  — Der Chillige (casual, analogies)
  Jarno — Der Dramatische (theatrical, apocalyptic)

Controls:
  SPACE / RIGHT / CLICK  — next slide
  LEFT                   — previous slide
  R                      — replay current audio
  S                      — skip audio (stop playback)
  Q / ESC                — quit
  F                      — toggle fullscreen
"""

import os
import sys
import wave
import io
import time
import subprocess
import shutil
import signal
from pathlib import Path

try:
    import pygame
    import fitz
    from PIL import Image
    from piper.voice import PiperVoice
    from piper.config import SynthesisConfig
except ImportError as e:
    print(f"Missing: {e}")
    print("Activate venv: source .venv/bin/activate")
    print("Then: pip install piper-tts pymupdf pygame Pillow")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
VOICES_DIR = SCRIPT_DIR / "voices"
CACHE_DIR = SCRIPT_DIR / "audio_cache"
PDF_PATH = SCRIPT_DIR / "Agentic_Shield_Zero_Trust.pdf"
GIF_PATH = SCRIPT_DIR / "morshu-zelda.gif"

# ── Presenter configs ──────────────────────────────────────────────

PRESENTERS = {
    "Mike": {
        "model": VOICES_DIR / "mike.onnx",
        "length_scale": 1.0,
        "noise_scale": 0.667,
        "noise_w_scale": 0.8,
        "color": (41, 128, 185),
        "title": "Der Ernste",
    },
    "Nico": {
        "model": VOICES_DIR / "nico.onnx",
        "length_scale": 0.88,
        "noise_scale": 0.8,
        "noise_w_scale": 0.9,
        "color": (231, 76, 60),
        "title": "Der Aufgeregte",
    },
    "Luca": {
        "model": VOICES_DIR / "luca.onnx",
        "length_scale": 1.12,
        "noise_scale": 0.5,
        "noise_w_scale": 0.7,
        "color": (46, 204, 113),
        "title": "Der Chillige",
    },
    "Jarno": {
        "model": VOICES_DIR / "jarno.onnx",
        "length_scale": 0.95,
        "noise_scale": 0.9,
        "noise_w_scale": 0.95,
        "color": (155, 89, 182),
        "title": "Der Dramatische",
    },
}

# ── Slide narrations (German, funny, personality-matched) ──────────

SLIDES = [
    # Slide 1 — Mike
    {
        "presenter": "Mike",
        "text": (
            "Willkommen, meine Damen und Herren. Mein Name ist Mike, "
            "und ich präsentiere heute etwas, das Ihre IT-Abteilung nachts "
            "wachhalten wird. Und zwar zurecht. "
            "Agentic Shield: Zero Trust für KI. "
            "Wir haben jahrzehntelang Mauern um unsere Netzwerke gebaut. "
            "Firewalls, IDS, DLP, SIEM — Milliarden investiert. "
            "Und dann haben wir eine Tür aufgemacht, durch die unser gesamter "
            "Security-Stack nicht hindurchsehen kann. "
            "Diese Tür ist der LLM-API-Call. "
            "Jedes Mal wenn ein Mitarbeiter Copilot fragt, jedes Mal wenn ein "
            "Kunde mit unserem Chatbot spricht — das ist Traffic, für den unsere "
            "Firewall komplett blind ist. "
            "Heute zeige ich euch warum das ein Problem ist, und was wir dagegen tun."
        ),
    },
    # Slide 2 — Nico
    {
        "presenter": "Nico",
        "text": (
            "Oh Mann, Leute, jetzt wird es richtig spannend! "
            "Ich bin Nico und ich muss euch was zeigen, das ist der absolute Wahnsinn! "
            "Schaut euch das an! Links seht ihr, wie eine normale Web Application Firewall "
            "einen SQL-Injection-Angriff blockt. Peng, erledigt, kennen wir. "
            "ABER, und jetzt haltet euch fest, rechts seht ihr, was passiert wenn "
            "jemand einen natürlichsprachlichen Prompt schickt. "
            "Der fließt einfach durch! Wie Wasser durch ein Sieb! "
            "Warum? Weil LLMs keine Privilege Rings haben! "
            "Kein Ring Zero, kein Kernel Mode, nichts! "
            "System-Prompt und User-Input, alles im selben Kontext-Fenster, "
            "alles gleich behandelt. "
            "Das ist als ob ihr euren Haustürschlüssel und euren Tresorschlüssel "
            "zusammenklebt und dann sagt, wird schon passen. Irre!"
        ),
    },
    # Slide 3 — Luca
    {
        "presenter": "Luca",
        "text": (
            "Hey Leute, ich bin der Luca. Alles easy, keine Panik. "
            "Also, Chatbots plappern, Agenten handeln, so einfach ist das. "
            "Stellt euch vor, ein Chatbot ist wie euer Kumpel der euch was erzählt "
            "am Stammtisch. Kann Blödsinn reden, ist aber harmlos. "
            "Ein Agent dagegen, der hat eure Kreditkarte, euren Wohnungsschlüssel "
            "und euer Email-Passwort. "
            "Wenn der Blödsinn macht, dann wird es teuer. "
            "Der Nutzer formuliert ein Ziel, der Agent plant Schritte, greift auf APIs zu, "
            "verändert Datenbanken. "
            "Das Risiko hat sich komplett verlagert. "
            "Früher war das Schlimmste ein dummer Kommentar vom Chatbot. "
            "Heute kann ein manipulierter Agent eure komplette Infrastruktur umgraben. "
            "Aber hey, kein Stress, dafür sind wir ja hier."
        ),
    },
    # Slide 4 — Jarno
    {
        "presenter": "Jarno",
        "text": (
            "Meine Damen und Herren, ich bin Jarno, und was ich euch jetzt zeige, "
            "das ist nichts Geringeres als die unheilige Dreifaltigkeit der KI-Sicherheit! "
            "Die Kill-Chain, die alles verändert! "
            "Oben haben wir LLM null sieben, System Prompt Leakage. "
            "Der Angreifer späht eure Verteidigungslinien aus, lernt eure Guardrails, "
            "kartografiert eure APIs! "
            "Dann, LLM null acht, Vector Poisoning! "
            "Payloads werden dauerhaft im RAG-Wissensspeicher platziert "
            "wie schlafende Agenten, bereit zum Zuschlagen! "
            "Und schließlich, LLM null eins, Prompt Injection! Die Waffe wird abgefeuert! "
            "Und das Perfide? Diese drei Schwachstellen sind keine isolierten Bugs. "
            "Sie verketten sich zu Compound Attacks, die jede Single-Layer-Defense zerreißen!"
        ),
    },
    # Slide 5 — Mike
    {
        "presenter": "Mike",
        "text": (
            "Mike wieder hier. Schauen wir uns einen konkreten Angriff an. "
            "Kein Theorie-Szenario, sondern ein echter, demonstrierter Angriff. "
            "ConfusedPilot, durchgeführt von Forschern der University of Texas "
            "gegen Microsoft 365 Copilot. "
            "Schritt eins: Der Angreifer versteckt unsichtbaren Text in einem PDF. "
            "Weißer Text auf weißem Hintergrund, für Menschen nicht sichtbar. "
            "Schritt zwei: Das RAG-System liest das Dokument ganz normal in die "
            "Vector Database ein. Nichts auffälliges. "
            "Schritt drei: Ein ahnungsloser Mitarbeiter bittet das LLM um eine Zusammenfassung. "
            "Schritt vier: Der versteckte Prompt wird ausgeführt, und das LLM exfiltriert "
            "Session-Daten über eine gerenderte Bild-URL. "
            "Und jetzt kommt der entscheidende Punkt: "
            "Der Nutzer hat nichts falsch gemacht. Das Modell hat perfekt funktioniert. "
            "Genau das ist das Problem."
        ),
    },
    # Slide 6 — Nico
    {
        "presenter": "Nico",
        "text": (
            "Nico ist zurück, und Leute, jetzt müsst ihr zuhören! "
            "Euer SOC, euer gesamtes Security Operations Center, ist blind! "
            "Und ich beweise es euch! "
            "Die WAF? Sieht validen JSON-Traffic! "
            "Weil Prompt Injection keine SQL-Injection ist. "
            "Es ist natürliche Sprache! Grammatisch korrekt, syntaktisch valide, "
            "semantisch vernichtend! "
            "IAM? Sieht eine valide API-Anfrage! Weil der Agent seine eigenen "
            "Credentials benutzt. Er wird zum Confused Deputy! "
            "DLP? Sieht eine gut formatierte, hilfreiche Antwort! "
            "Weil die Daten durch den normalen Antwortkanal des Modells abfließen! "
            "Und EDR? Sieht keinen Malware-Binary! "
            "Weil die Angriffsfläche das Context Window ist, nicht das Betriebssystem! "
            "Das ist wie wenn ein Einbrecher durch die Haustür spaziert, "
            "dem Sicherheitsdienst zulächelt, und der sagt: "
            "Der sieht nett aus, lass ihn rein! Wahnsinn!"
        ),
    },
    # Slide 7 — Luca
    {
        "presenter": "Luca",
        "text": (
            "So, ich bin es wieder, der Luca. "
            "Und nach all dem Drama von meinen Kollegen, ja ich schau dich an Jarno, "
            "kommen wir jetzt zur Lösung. Agentic Shield. Architektur statt Pflaster. "
            "Stellt euch vor: Links habt ihr den ganzen chaotischen, unberechenbaren "
            "KI-Kram. Prompts, RAG-Kontext, das Modell selbst. Alles untrusted. "
            "Rechts habt ihr eure wertvollen Enterprise-Ressourcen. "
            "APIs, Datenbanken, CI CD. "
            "Und dazwischen? Die Control Plane. "
            "Wie ein Türsteher im Club, der jeden einzeln prüft. "
            "Drei Grundregeln, ganz easy: "
            "Erstens, Zero Trust für KI. Kein Agent spricht jemals direkt mit "
            "kritischen Systemen. "
            "Zweitens, Separation of Concerns. Das Modell ist nicht für seine eigene "
            "Sicherheit zuständig. "
            "Drittens, deterministische Kontrolle. Jede Aktion wird außerhalb "
            "des LLMs validiert. Simpel, oder?"
        ),
    },
    # Slide 8 — Jarno
    {
        "presenter": "Jarno",
        "text": (
            "Jarno hier, und bestaunt die Festung, die wir errichten! "
            "Sechs Schichten der Verteidigung! "
            "Layer eins, der Network Sentinel, inspiziert jeden einzelnen API-Call "
            "am Netzwerk-Egress! "
            "Layer zwei, die Prompt Firewall, Classifier-basierte Injection-Detection "
            "und Encoding-Screening! Jeder verdächtige Prompt wird abgefangen! "
            "Layer drei, der System Vault, Credentials bleiben in externen Tresoren, "
            "niemals im Prompt! "
            "Layer vier, RAG Security, Permission-aware Embeddings, Provenance-Tagging, "
            "Hidden-Text-Scanning! "
            "Layer fünf, der Output Guardian, PII-Masking mit Presidio, "
            "Hallucination Cross-Referencing! "
            "Und Layer sechs, SOC Integration, Centralized Tracing und Anomaly Detection! "
            "Sechs Schichten! Jede mit einem anderen Erkennungsmechanismus! "
            "Ein Angreifer müsste alle überwinden!"
        ),
    },
    # Slide 9 — Mike
    {
        "presenter": "Mike",
        "text": (
            "Mike hier, und jetzt wird es technisch. "
            "Der Runtime Enforcement Loop. Sicherheit in Millisekunden. "
            "Sechs Schritte, die bei jeder einzelnen Interaktion ablaufen. "
            "Erstens: Observe. Input und Kontext werden klassifiziert. "
            "Zweitens: Plan. Der Agentenplan wird extrahiert und analysiert. "
            "Was hat der Agent vor? "
            "Drittens: Decide. Der Policy Decision Point prüft RBAC, Risiko und Kosten. "
            "Deterministisch, nicht vom LLM gesteuert. "
            "Viertens: Act. Das Tool-Gateway führt die Aktion nur über eine Allowlist aus. "
            "Fünftens: Verify. Output und Nebenwirkungen werden geprüft. "
            "Und sechstens: Learn. Der gesamte Trace geht ans SIEM, "
            "Detection-Regeln werden aktualisiert. "
            "Und im Zentrum steht: Human-in-the-Loop ist zwingend bei irreversiblen "
            "oder externen Aktionen. Eine E-Mail senden, eine Datenbank ändern, "
            "da fragt das System erst nach."
        ),
    },
    # Slide 10 — Nico
    {
        "presenter": "Nico",
        "text": (
            "Ich bin so begeistert von dieser Folie! Nico hier! "
            "Und schaut euch an wie der Shield die Kill-Chain zerschmettert! "
            "Erinnert ihr euch an die unheilige Dreifaltigkeit? "
            "LLM null sieben, null eins, null acht? "
            "Links seht ihr die Bedrohung. Der Angreifer versucht "
            "Prompt Injection, System Prompt Extraction und Data Exfiltration. "
            "Und rechts? Transformation! "
            "Die drei Schilde zerbrechen die Kill-Chain! "
            "Layer drei, der System Vault, Canary Tokens triggern sofort einen Alarm "
            "wenn jemand die Guardrails abfragen will! "
            "Layer zwei, die Prompt Firewall, semantische Evaluation droppt Payloads "
            "bevor das LLM sie überhaupt verarbeitet! "
            "Layer vier, RAG Security, alle eingespeisten Daten werden von unsichtbaren "
            "Zeichen gereinigt und an Access Levels gebunden! "
            "Die Kill-Chain? Gebrochen! Zerstört! Pulverisiert!"
        ),
    },
    # Slide 11 — Luca
    {
        "presenter": "Luca",
        "text": (
            "Hey, Luca hier nochmal. Reden wir über was Wichtiges. "
            "Eure Daten und die DSGVO. "
            "Weil Leute, wenn ihr vertrauliche Daten einfach so in ein "
            "LLM Context Window schiebt, dann ist das kein Feature, "
            "das ist ein Albtraum. "
            "Agentic Shield behandelt vertrauliche Daten nicht als normales Kontextmaterial. "
            "Schritt eins: Detect. PII, Secrets, IDs werden identifiziert. "
            "Schritt zwei: Minimize. Redaction vor dem Model-Call. "
            "Schritt drei: Isolate. Sensible Workloads laufen in dedizierten Tenants. "
            "Schritt vier: Control. Purpose Binding und Export-Restrictions. "
            "Und Schritt fünf: Prove. Audit Trail mit Hashes, alles nachweisbar. "
            "Denn Leute, Artikel 83 DSGVO ist kein Spaß. "
            "Bis zu 20 Millionen Euro oder vier Prozent des weltweiten Jahresumsatzes. "
            "KI-Kontextfenster sind keine sicheren Datenbanken. "
            "Aber jetzt wisst ihr, wie man es richtig macht."
        ),
    },
    # Slide 12 — Jarno
    {
        "presenter": "Jarno",
        "text": (
            "Jarno spricht! Und hört mir gut zu! "
            "Wir bauen hier keine neue Schatten-IT auf! "
            "Kein isoliertes Silo! Kein Elfenbeinturm! "
            "Agentic Shield integriert sich nahtlos in euer bestehendes "
            "Splunk oder Sentinel SIEM! "
            "In der Dev-Phase: Threat Modeling, AI Bill of Materials, Prompt Tests. "
            "Beim Deploy: Config Baselines und strikte Tool-Allowlists. "
            "Zur Runtime: Telemetrie gemappt auf MITRE ATLAS, "
            "den Standard für adversarial Machine Learning! "
            "Und beim Respond: SOAR Integration, automatisierter Kill-Switch "
            "und Incident Evidence Export! "
            "Von der Entwicklung bis zum Incident Response. "
            "Alles durchgeplant, alles integriert, nichts dem Zufall überlassen!"
        ),
    },
    # Slide 13 — Mike
    {
        "presenter": "Mike",
        "text": (
            "Mike zum letzten Mal, und jetzt wird es konkret. "
            "Die 90-Tage Rollout Roadmap. "
            "Phase eins, die ersten 30 Tage: Inventory und Visibility. "
            "Wir erfassen alle Agenten, Shadow-AI, Tools und Datenquellen. "
            "Der Network Sentinel geht live. "
            "Wir wissen endlich, was in unserem Netzwerk an KI-Traffic läuft. "
            "Phase zwei, Tag 31 bis 60: Control Plane MVP. "
            "Prompt Firewall und RAG Gateway für zwei Pilot-Use-Cases. "
            "Scoped Tokens statt Vollzugriff. "
            "Phase drei, Tag 61 bis 90: Policy Hardening. "
            "Default-Deny für Tools. Approval Flows mit Human-in-the-Loop. "
            "Und Red-Team Tests gegen die gesamte Architektur. "
            "Phase vier, ab Tag 90: Scale und Operate. "
            "Mandantenfähige Plattform ausrollen, SecOps Playbooks scharfschalten. "
            "Strategie: Zentrale Plattform, nicht isolierte SDKs in jedem Team."
        ),
    },
    # Slide 14 — Nico
    {
        "presenter": "Nico",
        "text": (
            "Letzte Folie Leute, und Nico gibt euch den finalen Weckruf! "
            "Die Frage ist nicht, ob eure LLMs angegriffen werden. "
            "Die Frage ist, ob ihr es merkt, wenn es passiert! "
            "Und jetzt mal ehrlich, mit eurem jetzigen Setup? Merkt ihr es nicht! "
            "Deshalb: Zentrale Control Plane statt isolierter Silos beauftragen! "
            "OWASP Top 10 for LLMs in den Architekturstandard aufnehmen! "
            "Agentic Shield Pilot auf zwei kritische Use-Cases starten. "
            "HR und Code-Gen zum Beispiel! "
            "Und einen verbindlichen Kill-Switch im SOC Runbook verankern! "
            "Das Fenster ist jetzt offen, Leute! "
            "LLM-Adoption beschleunigt, Security hinkt hinterher, Regulierung zieht an. "
            "Wer jetzt handelt, hat einen Vorsprung. "
            "Wer wartet, naja, der liest irgendwann seinen System-Prompt auf Twitter. "
            "Vielen Dank!"
        ),
    },
]

# ── Audio generation ───────────────────────────────────────────────

def generate_audio():
    CACHE_DIR.mkdir(exist_ok=True)
    voices = {}

    total = len(SLIDES)
    for i, slide in enumerate(SLIDES):
        out_path = CACHE_DIR / f"slide_{i:02d}.wav"
        if out_path.exists() and out_path.stat().st_size > 0:
            print(f"  [{i+1}/{total}] cached: {slide['presenter']}")
            continue
        if out_path.exists():
            out_path.unlink()

        name = slide["presenter"]
        cfg = PRESENTERS[name]

        if name not in voices:
            print(f"  Loading voice model: {name}...", end=" ", flush=True)
            voices[name] = PiperVoice.load(str(cfg["model"]))
            print("OK")

        print(f"  [{i+1}/{total}] generating: {name} — Slide {i+1}...", flush=True)
        voice = voices[name]

        syn_config = SynthesisConfig(
            length_scale=cfg["length_scale"],
            noise_scale=cfg["noise_scale"],
            noise_w_scale=cfg["noise_w_scale"],
        )

        audio_bytes = b""
        for chunk in voice.synthesize(slide["text"], syn_config):
            audio_bytes += chunk.audio_int16_bytes

        sample_rate = voice.config.sample_rate
        channels = 1
        sample_width = 2

        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_bytes)

    print("  All audio ready.\n")


# ── PDF rendering ─────────────────────────────────────────────────

def load_slides_as_surfaces(screen_w, screen_h):
    doc = fitz.open(str(PDF_PATH))
    surfaces = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        # calculate zoom to fit screen while maintaining aspect ratio
        page_rect = page.rect
        scale_x = screen_w / page_rect.width
        scale_y = screen_h / page_rect.height
        scale = min(scale_x, scale_y)
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat)
        mode = "RGBA" if pix.alpha else "RGB"
        img = pygame.image.frombuffer(pix.samples, (pix.width, pix.height), mode)
        surfaces.append(img)
    doc.close()
    return surfaces


# ── Animated speaker GIF ──────────────────────────────────────────

def load_speaker_frames(scale=2.0):
    """Load GIF frames, tint per presenter color, remove black bg."""
    if not GIF_PATH.exists():
        print(f"  Speaker GIF not found: {GIF_PATH}")
        return {}

    gif = Image.open(str(GIF_PATH))
    raw_frames = []
    for i in range(gif.n_frames):
        gif.seek(i)
        frame = gif.convert("RGBA")
        raw_frames.append(frame)

    TARGET_R, TARGET_G, TARGET_B = 235, 78, 10  # #eb4e0a
    TOLERANCE = 60

    speaker_frames = {}
    for name, cfg in PRESENTERS.items():
        tint_r, tint_g, tint_b = cfg["color"]
        tinted = []
        for frame in raw_frames:
            pixels = frame.load()
            w, h = frame.size
            new_frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            new_pixels = new_frame.load()
            for y in range(h):
                for x in range(w):
                    r, g, b, a = pixels[x, y]
                    brightness = (r + g + b) / 3.0
                    if brightness < 30:
                        new_pixels[x, y] = (0, 0, 0, 0)
                    elif (abs(r - TARGET_R) < TOLERANCE and
                          abs(g - TARGET_G) < TOLERANCE and
                          abs(b - TARGET_B) < TOLERANCE):
                        factor = brightness / 255.0
                        nr = min(255, int(tint_r * factor))
                        ng = min(255, int(tint_g * factor))
                        nb = min(255, int(tint_b * factor))
                        new_pixels[x, y] = (nr, ng, nb, a)
                    else:
                        new_pixels[x, y] = (r, g, b, a)

            if scale != 1.0:
                new_w = int(w * scale)
                new_h = int(h * scale)
                new_frame = new_frame.resize((new_w, new_h), Image.NEAREST)

            data = new_frame.tobytes()
            surf = pygame.image.frombuffer(data, new_frame.size, "RGBA")
            tinted.append(surf)
        speaker_frames[name] = tinted
        print(f"  Speaker frames loaded: {name} ({len(tinted)} frames)")

    return speaker_frames


# ── Presentation engine ───────────────────────────────────────────

def draw_presenter_badge(screen, name, slide_idx, total, font_big, font_small):
    cfg = PRESENTERS[name]
    badge_text = f"{name} — {cfg['title']}"
    progress_text = f"{slide_idx + 1} / {total}"

    badge_surf = font_big.render(badge_text, True, (255, 255, 255))
    progress_surf = font_small.render(progress_text, True, (200, 200, 200))

    pad_x, pad_y = 20, 10
    badge_w = badge_surf.get_width() + pad_x * 2
    badge_h = badge_surf.get_height() + pad_y * 2

    badge_bg = pygame.Surface((badge_w, badge_h), pygame.SRCALPHA)
    r, g, b = cfg["color"]
    pygame.draw.rect(badge_bg, (r, g, b, 220), (0, 0, badge_w, badge_h),
                     border_radius=12)
    badge_bg.blit(badge_surf, (pad_x, pad_y))

    screen_w = screen.get_width()
    screen_h = screen.get_height()

    screen.blit(badge_bg, (20, screen_h - badge_h - 20))

    prog_x = screen_w - progress_surf.get_width() - 30
    prog_y = screen_h - progress_surf.get_height() - 28
    prog_bg = pygame.Surface(
        (progress_surf.get_width() + 20, progress_surf.get_height() + 12),
        pygame.SRCALPHA,
    )
    pygame.draw.rect(
        prog_bg, (0, 0, 0, 160),
        (0, 0, prog_bg.get_width(), prog_bg.get_height()),
        border_radius=8,
    )
    screen.blit(prog_bg, (prog_x - 10, prog_y - 6))
    screen.blit(progress_surf, (prog_x, prog_y))


def draw_controls_hint(screen, font):
    hints = "SPACE/→ next  |  ← back  |  R replay  |  S skip  |  Q quit  |  F fullscreen"
    hint_surf = font.render(hints, True, (150, 150, 150))
    x = (screen.get_width() - hint_surf.get_width()) // 2
    y = 8
    bg = pygame.Surface((hint_surf.get_width() + 16, hint_surf.get_height() + 8),
                        pygame.SRCALPHA)
    pygame.draw.rect(bg, (0, 0, 0, 100),
                     (0, 0, bg.get_width(), bg.get_height()), border_radius=6)
    screen.blit(bg, (x - 8, y - 4))
    screen.blit(hint_surf, (x, y))


_audio_proc = None

def _find_player():
    for cmd in ("pw-play", "paplay", "aplay", "ffplay"):
        if shutil.which(cmd):
            return cmd
    return None

_PLAYER = _find_player()

def play_audio(slide_idx):
    global _audio_proc
    stop_audio()

    audio_path = str(CACHE_DIR / f"slide_{slide_idx:02d}.wav")
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
        return

    if not _PLAYER:
        print("  No audio player found (tried pw-play, paplay, aplay, ffplay)")
        return

    try:
        if _PLAYER == "ffplay":
            cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", audio_path]
        else:
            cmd = [_PLAYER, audio_path]
        _audio_proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"  Audio error slide {slide_idx}: {e}")


def stop_audio():
    global _audio_proc
    if _audio_proc and _audio_proc.poll() is None:
        _audio_proc.terminate()
        try:
            _audio_proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            _audio_proc.kill()
    _audio_proc = None


def audio_playing():
    return _audio_proc is not None and _audio_proc.poll() is None


def fade_transition(screen, old_surf, new_surf, slide_img_rect, duration_ms=400):
    clock = pygame.time.Clock()
    steps = max(1, duration_ms // 16)
    for step in range(steps + 1):
        alpha = int(255 * step / steps)
        screen.fill((0, 0, 0))
        if old_surf:
            old_surf.set_alpha(255 - alpha)
            screen.blit(old_surf, slide_img_rect)
        new_surf.set_alpha(alpha)
        screen.blit(new_surf, slide_img_rect)
        pygame.display.flip()
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
    new_surf.set_alpha(255)
    return True


def render_frame(screen, slide_surfaces, current, num_slides,
                 speaker_frames, gif_frame_idx, font_big, font_small, font_hint,
                 show_controls):
    surf = slide_surfaces[current]
    sw, sh = screen.get_width(), screen.get_height()
    img_x = (sw - surf.get_width()) // 2
    img_y = (sh - surf.get_height()) // 2

    screen.fill((0, 0, 0))
    screen.blit(surf, (img_x, img_y))

    presenter = SLIDES[current]["presenter"]
    draw_presenter_badge(screen, presenter, current, num_slides, font_big, font_small)

    if speaker_frames and presenter in speaker_frames:
        frames = speaker_frames[presenter]
        if frames:
            frame_surf = frames[gif_frame_idx % len(frames)]
            gx = sw - frame_surf.get_width() - 30
            gy = sh - frame_surf.get_height() - 20
            screen.blit(frame_surf, (gx, gy))

    if show_controls:
        draw_controls_hint(screen, font_hint)

    pygame.display.flip()


def run_presentation():
    pygame.init()

    info = pygame.display.Info()
    screen_w, screen_h = info.current_w, info.current_h
    fullscreen = True
    screen = pygame.display.set_mode((screen_w, screen_h), pygame.FULLSCREEN)
    pygame.display.set_caption("Agentic Shield — Presentation")
    pygame.mouse.set_visible(False)

    try:
        font_big = pygame.font.SysFont("DejaVu Sans,Arial,Helvetica", 28, bold=True)
        font_small = pygame.font.SysFont("DejaVu Sans,Arial,Helvetica", 20)
        font_hint = pygame.font.SysFont("DejaVu Sans,Arial,Helvetica", 16)
    except Exception:
        font_big = pygame.font.Font(None, 32)
        font_small = pygame.font.Font(None, 24)
        font_hint = pygame.font.Font(None, 18)

    print("Loading PDF slides...")
    slide_surfaces = load_slides_as_surfaces(screen_w, screen_h)
    num_slides = min(len(slide_surfaces), len(SLIDES))

    print("Loading speaker GIF...")
    speaker_frames = load_speaker_frames(scale=2.0)

    print(f"Loaded {num_slides} slides. Starting presentation.\n")

    current = 0
    prev_surface = None
    clock = pygame.time.Clock()
    auto_advance = True
    need_slide_change = True
    need_transition = True
    show_controls = True
    controls_timer = time.time()
    gif_frame_idx = 0
    gif_paused_frame = 0
    last_gif_advance = time.time()
    gif_interval = 0.1
    audio_was_playing = False
    audio_done_time = None

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                stop_audio()
                pygame.quit()
                return

            if event.type == pygame.KEYDOWN:
                show_controls = True
                controls_timer = time.time()

                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    stop_audio()
                    pygame.quit()
                    return

                elif event.key in (pygame.K_SPACE, pygame.K_RIGHT):
                    stop_audio()
                    audio_done_time = None
                    if current < num_slides - 1:
                        prev_surface = slide_surfaces[current].copy()
                        current += 1
                        need_slide_change = True
                        need_transition = True
                    else:
                        pygame.quit()
                        return

                elif event.key == pygame.K_LEFT:
                    stop_audio()
                    audio_done_time = None
                    if current > 0:
                        prev_surface = slide_surfaces[current].copy()
                        current -= 1
                        need_slide_change = True
                        need_transition = True

                elif event.key == pygame.K_r:
                    audio_done_time = None
                    play_audio(current)

                elif event.key == pygame.K_s:
                    stop_audio()

                elif event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode(
                            (screen_w, screen_h), pygame.FULLSCREEN
                        )
                        pygame.mouse.set_visible(False)
                    else:
                        w = int(screen_w * 0.8)
                        h = int(screen_h * 0.8)
                        screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
                        pygame.mouse.set_visible(True)
                    slide_surfaces = load_slides_as_surfaces(
                        screen.get_width(), screen.get_height()
                    )
                    need_slide_change = True
                    need_transition = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    stop_audio()
                    audio_done_time = None
                    if current < num_slides - 1:
                        prev_surface = slide_surfaces[current].copy()
                        current += 1
                        need_slide_change = True
                        need_transition = True

        if need_slide_change:
            surf = slide_surfaces[current]
            sw, sh = screen.get_width(), screen.get_height()
            img_x = (sw - surf.get_width()) // 2
            img_y = (sh - surf.get_height()) // 2
            img_rect = (img_x, img_y)

            if need_transition and prev_surface:
                fade_transition(
                    screen, prev_surface, surf.copy(), img_rect, duration_ms=350
                )

            play_audio(current)
            gif_frame_idx = 0
            audio_was_playing = True
            audio_done_time = None
            need_slide_change = False
            need_transition = False
            prev_surface = None

        is_playing = audio_playing()

        if is_playing:
            now = time.time()
            if now - last_gif_advance >= gif_interval:
                gif_frame_idx += 1
                last_gif_advance = now
            gif_paused_frame = gif_frame_idx
            audio_was_playing = True
            audio_done_time = None

        if audio_was_playing and not is_playing and audio_done_time is None:
            audio_done_time = time.time()
            audio_was_playing = False

        if show_controls and (time.time() - controls_timer > 5):
            show_controls = False

        render_frame(screen, slide_surfaces, current, num_slides,
                     speaker_frames, gif_paused_frame if not is_playing else gif_frame_idx,
                     font_big, font_small, font_hint, show_controls)

        if auto_advance and audio_done_time and (time.time() - audio_done_time > 1.2):
            if current < num_slides - 1:
                prev_surface = slide_surfaces[current].copy()
                current += 1
                need_slide_change = True
                need_transition = True
                audio_done_time = None

        clock.tick(30)


# ── Main ──────────────────────────────────────────────────────────

def main():
    if not PDF_PATH.exists():
        print(f"PDF not found: {PDF_PATH}")
        sys.exit(1)

    for name, cfg in PRESENTERS.items():
        if not cfg["model"].exists():
            print(f"Voice model missing for {name}: {cfg['model']}")
            print("Run: bash setup.sh")
            sys.exit(1)

    print("=" * 60)
    print("  AGENTIC SHIELD — Automated Presentation")
    print("  4 Presenters: Mike, Nico, Luca, Jarno")
    print("=" * 60)
    print()
    print("Generating audio (cached after first run)...")
    generate_audio()

    print("Launching presentation...")
    run_presentation()


if __name__ == "__main__":
    main()

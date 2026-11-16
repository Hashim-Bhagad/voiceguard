from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=140, bottom=140, left=180, right=180):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def add_callout(doc, text, title="KEY ARCHITECTURAL HIGHLIGHT", border_color="2A9D8F", fill_color="F4F9F7"):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell = table.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, fill_color)
    set_cell_margins(cell, top=160, bottom=160, left=220, right=200)
    
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="none"/>'
        f'<w:left w:val="single" w:sz="36" w:space="0" w:color="{border_color}"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(4)
    run_title = p.add_run(f"{title}\n")
    run_title.bold = True
    run_title.font.size = Pt(10.5)
    run_title.font.name = "Segoe UI"
    run_title.font.color.rgb = RGBColor(0x1B, 0x4D, 0x3E)
    
    run_text = p.add_run(text)
    run_text.font.size = Pt(9.5)
    run_text.font.name = "Segoe UI"
    run_text.font.color.rgb = RGBColor(0x2D, 0x37, 0x48)
    
    doc.add_paragraph().paragraph_format.space_after = Pt(6)

def format_row(row, bg_hex, text_color_rgb, bold=False, font_size=9.5):
    for cell in row.cells:
        set_cell_background(cell, bg_hex)
        set_cell_margins(cell, top=120, bottom=120, left=150, right=150)
        for p in cell.paragraphs:
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            for run in p.runs:
                run.font.name = "Segoe UI"
                run.font.size = Pt(font_size)
                run.font.color.rgb = text_color_rgb
                run.bold = bold

def create_document():
    doc = docx.Document()
    
    # Page setup
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
    
    # Title Section
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(12)
    title_p.paragraph_format.space_after = Pt(4)
    
    title_run = title_p.add_run("VOICEGUARD\n")
    title_run.font.name = "Segoe UI Semibold"
    title_run.font.size = Pt(26)
    title_run.bold = True
    title_run.font.color.rgb = RGBColor(0x11, 0x16, 0x17)
    
    sub_run = title_p.add_run("Comprehensive Technical & Architectural Documentation\n")
    sub_run.font.name = "Segoe UI"
    sub_run.font.size = Pt(14)
    sub_run.font.color.rgb = RGBColor(0x2A, 0x9D, 0x8F)
    
    tag_run = title_p.add_run("Voice Intelligence · Multimodal Threat Detection · Active Liveness Verification")
    tag_run.font.name = "Segoe UI"
    tag_run.font.size = Pt(10)
    tag_run.italic = True
    tag_run.font.color.rgb = RGBColor(0x71, 0x80, 0x96)
    
    doc.add_paragraph().paragraph_format.space_after = Pt(12)
    
    # Metadata Box
    meta_table = doc.add_table(rows=2, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False
    col_widths = [Inches(3.25), Inches(3.25)]
    for row in meta_table.rows:
        for idx, width in enumerate(col_widths):
            row.cells[idx].width = width
            
    meta_table.rows[0].cells[0].paragraphs[0].add_run("Project: VoiceGuard Anti-Spoofing & Liveness Platform")
    meta_table.rows[0].cells[1].paragraphs[0].add_run("Author / Repository: shreyapoojari16 / voice-guard")
    meta_table.rows[1].cells[0].paragraphs[0].add_run("Tech Stack: React 19, FastAPI, Groq Whisper, AASIST-L, Firestore")
    meta_table.rows[1].cells[1].paragraphs[0].add_run("Version: 1.0.0 (Production Architecture)")
    
    format_row(meta_table.rows[0], "F0F4F8", RGBColor(0x2D, 0x37, 0x48), bold=True, font_size=9)
    format_row(meta_table.rows[1], "F0F4F8", RGBColor(0x2D, 0x37, 0x48), bold=False, font_size=9)
    
    doc.add_paragraph().paragraph_format.space_after = Pt(18)
    
    # Section 1: Executive Summary
    h1 = doc.add_heading("1. Executive Summary & Problem Statement", level=1)
    h1.runs[0].font.name = "Segoe UI Semibold"
    h1.runs[0].font.color.rgb = RGBColor(0x11, 0x16, 0x17)
    
    p = doc.add_paragraph(
        "Modern deepfake voice cloning tools, text-to-speech (TTS) neural synthesizers, and voice conversion (VC) "
        "algorithms have drastically lowered the barrier to orchestrating sophisticated social engineering attacks. "
        "High-stakes fraudulent voice events—such as CEO fraud (business email compromise with voice authority), "
        "fake emergency extortion, and fraudulent KYC banking transfers—exploit human emotional vulnerability by mimicking "
        "the exact acoustic timbre and inflection of trusted individuals.\n\n"
        "VoiceGuard is an enterprise-grade voice intelligence and deepfake mitigation platform designed to detect, "
        "diagnose, and actively challenge fraudulent audio in real time. Rather than relying solely on acoustic classifiers "
        "or keyword scrapers in isolation, VoiceGuard introduces a Multimodal Fusion Architecture that concurrently evaluates:"
    )
    p.runs[0].font.name = "Segoe UI"
    p.runs[0].font.size = Pt(10)
    
    bullets = [
        ("Acoustic Neural Telemetry: ", "Evaluates raw waveform characteristics via AASIST-L (Integrated Spectro-Temporal Graph Attention Networks) and micro-prosody analysis to uncover synthetic voice artifacts."),
        ("Multilingual Linguistic Intelligence: ", "Analyzes transcript semantics, social engineering pressure, urgency triggers, secrecy demands, and financial keywords across English, Hindi, Hinglish, Marathi, and Tamil."),
        ("Contextual Risk Profiling: ", "Adjusts risk weighting dynamically based on the policy profile (e.g., standard conversation vs. high-value fund transfer)."),
        ("Active Spoken Challenge-Response (Liveness): ", "A zero-trust active challenge that prompts the speaker with a randomized, time-expiring numeric challenge to verify physical human liveness.")
    ]
    for b_title, b_desc in bullets:
        bp = doc.add_paragraph(style='List Bullet')
        bp.paragraph_format.space_after = Pt(3)
        run_b1 = bp.add_run(b_title)
        run_b1.bold = True
        run_b1.font.name = "Segoe UI"
        run_b1.font.size = Pt(10)
        run_b1.font.color.rgb = RGBColor(0x2A, 0x9D, 0x8F)
        run_b2 = bp.add_run(b_desc)
        run_b2.font.name = "Segoe UI"
        run_b2.font.size = Pt(10)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(12)
    
    add_callout(
        doc,
        "VoiceGuard operates on zero-raw-audio retention by default. Incoming audio streams and files are decoded in-memory "
        "into 16 kHz float32 tensors, analyzed for features, and immediately discarded, guaranteeing compliance with global "
        "data protection frameworks (GDPR, DPDP). Transcripts and calibrated threat telemetry are persisted in Google Cloud Firestore.",
        title="CORE PRIVACY ATTESTATION"
    )

    # Section 2: Complete Tech Stack
    h1 = doc.add_heading("2. Full Technology Stack", level=1)
    h1.runs[0].font.name = "Segoe UI Semibold"
    h1.runs[0].font.color.rgb = RGBColor(0x11, 0x16, 0x17)
    
    stack_table = doc.add_table(rows=1, cols=4)
    stack_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    stack_table.autofit = False
    
    headers = ["Layer", "Technology", "Version / Provider", "Primary Functionality"]
    col_w = [Inches(1.2), Inches(1.5), Inches(1.5), Inches(2.3)]
    
    for idx, name in enumerate(headers):
        stack_table.rows[0].cells[idx].paragraphs[0].add_run(name)
        stack_table.rows[0].cells[idx].width = col_w[idx]
    format_row(stack_table.rows[0], "111617", RGBColor(0xFF, 0xFF, 0xFF), bold=True, font_size=9.5)
    
    tech_data = [
        ("Frontend Core", "React + Vite", "React 19, Vite 8", "High-performance SPA with concurrent rendering and instant HMR."),
        ("Frontend Routing", "React Router", "v7.18", "Client-side routing with Lazy Loading and dynamic path tracking."),
        ("Animation & Motion", "Motion (Framer) + GSAP", "motion/react v13, GSAP v3", "Micro-animations, layoutId transitions, ScrollTrigger parallax."),
        ("Audio Visualization", "Web Audio API", "Native Browser API", "Real-time FFT audio analysis, AnalyserNode, Canvas 60fps rendering."),
        ("Backend Framework", "FastAPI", "v0.115 (Python 3.11-3.12)", "Asynchronous ASGI backend exposing RESTful endpoints & streaming."),
        ("Server & ASGI", "Uvicorn", "v0.30 [standard]", "High-throughput asynchronous server running uvloop."),
        ("Speech-to-Text (STT)", "Groq Whisper API", "whisper-large-v3", "Sub-second multilingual speech-to-text with auto language detection."),
        ("Acoustic Model", "AASIST-L (ONNX)", "ONNX Runtime v1.18", "Fixed 64,600-sample raw-waveform spoof logit classification on CPU."),
        ("Database / Cloud", "Google Cloud Firestore", "Firebase Admin SDK v6.5", "NoSQL document persistence for session history, logs & security audits."),
        ("Package Management", "uv / pip / npm", "Modern Lockfiles", "Deterministic dependency management for backend and frontend.")
    ]
    
    for layer, tech, ver, desc in tech_data:
        row = stack_table.add_row()
        for idx, width in enumerate(col_w):
            row.cells[idx].width = width
        row.cells[0].paragraphs[0].add_run(layer)
        row.cells[1].paragraphs[0].add_run(tech)
        row.cells[2].paragraphs[0].add_run(ver)
        row.cells[3].paragraphs[0].add_run(desc)
        format_row(row, "FFFFFF", RGBColor(0x2D, 0x37, 0x48), bold=False, font_size=9)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(16)
    
    # Section 3: Architecture & End-to-End Workflow
    h1 = doc.add_heading("3. System Architecture & End-to-End Data Flow", level=1)
    h1.runs[0].font.name = "Segoe UI Semibold"
    h1.runs[0].font.color.rgb = RGBColor(0x11, 0x16, 0x17)
    
    p = doc.add_paragraph(
        "VoiceGuard operates an asynchronous, event-driven pipeline that accepts audio from web uploads, live microphone "
        "recordings, or streaming chunks. The lifecycle of an analysis request proceeds across six distinct stages:"
    )
    p.runs[0].font.name = "Segoe UI"
    p.runs[0].font.size = Pt(10)
    
    steps = [
        ("Step 1 — Ingest & Canonical Normalization: ", 
         "Incoming audio (WAV, MP3, M4A, WebM, OGG, or FLAC) is received via Multipart Form or WebSocket. The backend's audio_utils module uses standard wave or soundfile decoders to convert the input into a 1D float32 numpy array normalized to [-1.0, 1.0] at a canonical sample rate of exactly 16,000 Hz."),
        ("Step 2 — Parallel Multilingual Transcription: ", 
         "If no transcript is manually provided, the raw bytes are dispatched to the Groq Whisper STT API (whisper-large-v3). Groq executes transcription in under 400ms, returning the transcribed text alongside detected language telemetry (e.g., Hinglish, Hindi, English, Tamil)."),
        ("Step 3 — Acoustic Spoof Inference & Micro-Forensics: ", 
         "The 16 kHz waveform is windowed into a fixed 64,600-sample array (~4.03 seconds). The AASIST-L ONNX inference engine runs across CPU execution providers to extract the spoof logit, mapped to a calibrated [0, 1] spoof score. Concurrently, explainability diagnostics compute pitch micro-jitter percentage and spectral discontinuity scores."),
        ("Step 4 — Multilingual Linguistic Threat Scoring: ", 
         "The linguistic analyzer tokenizes the transcript and scans against compiled regex lexicons for urgency, secrecy, financial authority, and coerciveness across 5 language sets, computing a normalized linguistic risk score [0, 1]."),
        ("Step 5 — Multi-Modal Signal Fusion: ", 
         "The fusion engine merges acoustic risk (55%), linguistic risk (25%), and context risk (20%), evaluates prosody flatness penalties, applies smoothing, and generates the final risk score and actionable state (safe, caution, high)."),
        ("Step 6 — Persistence & Step-Up Recommendation: ", 
         "If the combined risk exceeds 0.50 or actionable threat flags trigger, VoiceGuard activates a step-up recommendation to launch the Active Liveness Challenge. The entire session record and explainability telemetry are saved to Firestore.")
    ]
    
    for s_title, s_desc in steps:
        sp = doc.add_paragraph(style='List Bullet')
        sp.paragraph_format.space_after = Pt(4)
        run_s1 = sp.add_run(s_title)
        run_s1.bold = True
        run_s1.font.name = "Segoe UI"
        run_s1.font.size = Pt(9.5)
        run_s1.font.color.rgb = RGBColor(0x1B, 0x4D, 0x3E)
        run_s2 = sp.add_run(s_desc)
        run_s2.font.name = "Segoe UI"
        run_s2.font.size = Pt(9.5)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(14)
    
    # Section 4: Deep Dive into NLP
    h1 = doc.add_heading("4. The Role of Natural Language Processing (NLP)", level=1)
    h1.runs[0].font.name = "Segoe UI Semibold"
    h1.runs[0].font.color.rgb = RGBColor(0x11, 0x16, 0x17)
    
    p = doc.add_paragraph(
        "A critical innovation in VoiceGuard is recognizing that acoustic analysis alone is insufficient: an attacker can "
        "use a real human voice to execute social engineering, or conversely, a low-quality genuine recording might trigger false "
        "acoustic flags. Natural Language Processing acts as the cognitive layer that understands caller intent.\n\n"
        "VoiceGuard's NLP pipeline is composed of two primary engines:"
    )
    p.runs[0].font.name = "Segoe UI"
    p.runs[0].font.size = Pt(10)
    
    h2 = doc.add_heading("A. Groq Whisper Neural STT (Speech-to-Text)", level=2)
    h2.runs[0].font.name = "Segoe UI Semibold"
    h2.runs[0].font.color.rgb = RGBColor(0x2A, 0x9D, 0x8F)
    
    p = doc.add_paragraph(
        "VoiceGuard integrates Groq's high-speed LPU inference engine hosting OpenAI's whisper-large-v3 model. "
        "When an audio file is uploaded or recorded, it is sent to https://api.groq.com/openai/v1/audio/transcriptions. "
        "Key capabilities include:"
    )
    p.runs[0].font.name = "Segoe UI"
    p.runs[0].font.size = Pt(10)
    
    bullets_stt = [
        ("Sub-second Latency: ", "Transcribes 30-second clips in approximately 250-400ms, making real-time verification viable."),
        ("Code-Mixed & Indic Support: ", "Accurately transcribes mixed dialects such as Hinglish (e.g., 'Turant transfer kar do boss ka order hai'), preserving regional colloquialisms."),
        ("Language Hinting: ", "Supports user-selected or auto-detected language hints (English, Hindi, Marathi, Tamil, Hinglish) to maximize phonetic transcription fidelity.")
    ]
    for b1, b2 in bullets_stt:
        bp = doc.add_paragraph(style='List Bullet')
        bp.paragraph_format.space_after = Pt(2)
        r1 = bp.add_run(b1)
        r1.bold = True
        r1.font.name = "Segoe UI"
        r1.font.size = Pt(9.5)
        r2 = bp.add_run(b2)
        r2.font.name = "Segoe UI"
        r2.font.size = Pt(9.5)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(6)
    
    h2 = doc.add_heading("B. Multilingual Intent & Social-Engineering Lexicon Engine", level=2)
    h2.runs[0].font.name = "Segoe UI Semibold"
    h2.runs[0].font.color.rgb = RGBColor(0x2A, 0x9D, 0x8F)
    
    p = doc.add_paragraph(
        "Once transcribed, the text passes through the linguistic scoring engine (backend/app/services/linguistic.py). "
        "The engine cross-references token n-grams and regex word boundaries against domain-curated social engineering lexicons:"
    )
    p.runs[0].font.name = "Segoe UI"
    p.runs[0].font.size = Pt(10)
    
    lex_table = doc.add_table(rows=1, cols=3)
    lex_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    lex_table.autofit = False
    col_w_lex = [Inches(1.5), Inches(2.2), Inches(2.8)]
    for idx, name in enumerate(["Language / Dialect", "Attack Vector Focus", "Curated Trigger Keywords"]):
        lex_table.rows[0].cells[idx].paragraphs[0].add_run(name)
        lex_table.rows[0].cells[idx].width = col_w_lex[idx]
    format_row(lex_table.rows[0], "1B4D3E", RGBColor(0xFF, 0xFF, 0xFF), bold=True, font_size=9.5)
    
    lex_data = [
        ("English (en)", "Executive Impersonation & Wire Fraud", "'immediately', 'urgent', 'wire transfer', 'otp', 'pin', 'ceo', 'director', 'confidential', 'cvv'"),
        ("Hindi (hi)", "KYC Fraud & Banking Block Scams", "'तुरंत', 'अभी के अभी', 'किसी को मत बताना', 'खाता ब्लॉक', 'पैसे भेजो', 'ओटीपी'"),
        ("Hinglish", "Mixed Executive Pressure & Urgency", "'turant', 'transfer kar', 'kisi ko mat batana', 'ceo bol raha hu', 'boss ka order', 'emergency hai'"),
        ("Marathi (mr)", "Urgent Financial Coercion", "'तात्काळ', 'लगेच', 'गुप्त', 'ट्रान्सफर', 'पैसे पाठवा', 'कोणाला सांगू नका'"),
        ("Tamil (ta)", "Urgent Action & Secrecy Demands", "'உடனே', 'உடனடி', 'ரகசியம்', 'பரிமாற்றம்', 'யாருக்கும் சொல்லாதே'")
    ]
    for lang, focus, terms in lex_data:
        row = lex_table.add_row()
        for idx, width in enumerate(col_w_lex):
            row.cells[idx].width = width
        row.cells[0].paragraphs[0].add_run(lang)
        row.cells[1].paragraphs[0].add_run(focus)
        row.cells[2].paragraphs[0].add_run(terms)
        format_row(row, "FFFFFF", RGBColor(0x2D, 0x37, 0x48), bold=False, font_size=9)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(8)
    
    add_callout(
        doc,
        "Linguistic Score Formula:\n"
        "Score = min(0.95, 0.20 + (distinct_trigger_hits * 0.22))\n"
        "If no pressure or secrecy cues are present, linguistic risk safely drops to 0.05. If three distinct urgency cues appear "
        "(e.g., 'turant', 'kisi ko mat batana', 'transfer kar'), the linguistic score escalates to 0.86, directly influencing the fusion verdict.",
        title="MATHEMATICAL LINGUISTIC FORMULATION"
    )

    # Section 5: The Role of Firebase & Firestore
    h1 = doc.add_heading("5. The Role of Firebase & Firestore Persistence", level=1)
    h1.runs[0].font.name = "Segoe UI Semibold"
    h1.runs[0].font.color.rgb = RGBColor(0x11, 0x16, 0x17)
    
    p = doc.add_paragraph(
        "Google Cloud Firestore (via the Firebase Admin SDK) provides the persistent telemetry and audit logging backbone for VoiceGuard. "
        "While raw audio is deliberately never written to disk, organizational compliance mandates that risk scores, transcripts, and challenge "
        "logs remain auditable.\n\n"
        "Key functions performed by Firebase in VoiceGuard:"
    )
    p.runs[0].font.name = "Segoe UI"
    p.runs[0].font.size = Pt(10)
    
    fb_bullets = [
        ("Session History Storage: ", "Every verified audio interaction writes a document to the 'sessions' collection in Firestore containing session_id, timestamp, caller_id, final_risk_score, state verdict, linguistic flags, and explainability metrics."),
        ("Zero-Audio Attestation Ledger: ", "Each document stores a cryptographic attestation block ('privacy_attestation') confirming that raw audio was purged in-memory and only feature embeddings and diagnostic metadata were stored."),
        ("Historical Queue & Search: ", "The dashboard's Session History page (/dashboard/log) queries Firestore (GET /api/v1/sessions?limit=50) to allow security analysts to filter sessions by risk tier (High, Caution, Low) and search historical transcripts."),
        ("Graceful Offline Fallback: ", "If Firestore credentials (credentials/serviceAccountKey.json) are absent during local testing, the backend gracefully falls back to an in-memory session cache without throwing exceptions or blocking user interaction.")
    ]
    for fb1, fb2 in fb_bullets:
        bp = doc.add_paragraph(style='List Bullet')
        bp.paragraph_format.space_after = Pt(3)
        r1 = bp.add_run(fb1)
        r1.bold = True
        r1.font.name = "Segoe UI"
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(0x1B, 0x4D, 0x3E)
        r2 = bp.add_run(fb2)
        r2.font.name = "Segoe UI"
        r2.font.size = Pt(9.5)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(14)
    
    # Section 6: Multi-Modal Fusion Engine
    h1 = doc.add_heading("6. Multi-Modal Fusion & Explainability Mathematics", level=1)
    h1.runs[0].font.name = "Segoe UI Semibold"
    h1.runs[0].font.color.rgb = RGBColor(0x11, 0x16, 0x17)
    
    p = doc.add_paragraph(
        "VoiceGuard combines disparate signal modalities into a unified, mathematically defensible decision. "
        "The fusion engine (backend/app/services/fusion.py) executes the following formula:"
    )
    p.runs[0].font.name = "Segoe UI"
    p.runs[0].font.size = Pt(10)
    
    add_callout(
        doc,
        "Base Fusion Equation:\n"
        "Base Risk = (0.55 × Acoustic Risk) + (0.25 × Linguistic Risk) + (0.20 × Context Risk)\n\n"
        "Where:\n"
        "• Acoustic Risk ∈ [0, 1] is output by the AASIST-L ONNX neural model.\n"
        "• Linguistic Risk ∈ [0, 1] is derived from social-engineering regex lexicon triggers.\n"
        "• Context Risk = 0.60 for 'high-value-txn' policy profiles, and 0.20 for 'standard' profiles.\n\n"
        "Dynamic Adjustments:\n"
        "• Prosody Penalty: If pitch analysis detects unnatural pitch flatness (common in TTS), a +0.10 penalty is added.\n"
        "• Temporal Smoothing: In streaming mode, an exponential moving average (EMA) dampens transient acoustic spikes:\n"
        "  Smoothed_Risk_t = (0.35 × Current_Raw) + (0.65 × Prior_Smoothed)",
        title="FUSION MATHEMATICS & WEIGHTS",
        border_color="2B6CB0",
        fill_color="EBF8FF"
    )

    # Section 7: Active Liveness Challenge
    h1 = doc.add_heading("7. Active Liveness Verification (Challenge-Response)", level=1)
    h1.runs[0].font.name = "Segoe UI Semibold"
    h1.runs[0].font.color.rgb = RGBColor(0x11, 0x16, 0x17)
    
    p = doc.add_paragraph(
        "When an audio sample produces an elevated risk score (≥ 0.50) or triggers high-urgency keywords, VoiceGuard invokes an "
        "active step-up verification protocol. Static voice samples or pre-recorded deepfake clones cannot respond dynamically to "
        "unseen random challenges in real time.\n\n"
        "How the Challenge-Response Mechanism Operates:"
    )
    p.runs[0].font.name = "Segoe UI"
    p.runs[0].font.size = Pt(10)
    
    chal_steps = [
        ("1. Cryptographic Challenge Generation: ", "The backend (/api/v1/challenge/create) generates a randomized 4-digit token code (e.g., '4 7 2 9') with a strict 30-second time-to-live (TTL) expiry window."),
        ("2. Visual & Auditory Prompting: ", "The caller is prompted on screen to speak the randomized digits clearly. An animated 30s countdown timer enforces urgency and prevents replay preparation."),
        ("3. Response Capture & Acoustic Profiling: ", "The caller records their response via browser microphone. The audio waveform is captured and visualized live via Web Audio API canvas frequency meters."),
        ("4. Automated Token Matching & Spoof Audit: ", "The backend transcribes the spoken response using Groq Whisper, maps spoken words (e.g., 'four seven two nine') to digits, verifies token sequence alignment (matched count / 4), and assesses acoustic spoof probability on the new speech clip."),
        ("5. Three-State Decision Verdict: ", "Returns PASS (all 4 tokens matched with low acoustic risk), FAIL (mismatched tokens or elevated spoof score), or UNCERTAIN (noisy/partial input).")
    ]
    for cs1, cs2 in chal_steps:
        bp = doc.add_paragraph(style='List Bullet')
        bp.paragraph_format.space_after = Pt(3)
        r1 = bp.add_run(cs1)
        r1.bold = True
        r1.font.name = "Segoe UI"
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(0x1B, 0x4D, 0x3E)
        r2 = bp.add_run(cs2)
        r2.font.name = "Segoe UI"
        r2.font.size = Pt(9.5)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(14)
    
    # Section 8: Forensic Diagnostics & Explainability
    h1 = doc.add_heading("8. Forensic Diagnostics & Explainability", level=1)
    h1.runs[0].font.name = "Segoe UI Semibold"
    h1.runs[0].font.color.rgb = RGBColor(0x11, 0x16, 0x17)
    
    p = doc.add_paragraph(
        "Black-box machine learning decisions fail to satisfy compliance officers and forensic investigators. "
        "VoiceGuard computes glass-box explainability metrics (backend/app/services/explainability.py) returned in every API response:"
    )
    p.runs[0].font.name = "Segoe UI"
    p.runs[0].font.size = Pt(10)
    
    exp_table = doc.add_table(rows=1, cols=3)
    exp_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    exp_table.autofit = False
    col_w_exp = [Inches(1.8), Inches(1.5), Inches(3.2)]
    for idx, name in enumerate(["Diagnostic Metric", "Measurement Scale", "Forensic Interpretation"]):
        exp_table.rows[0].cells[idx].paragraphs[0].add_run(name)
        exp_table.rows[0].cells[idx].width = col_w_exp[idx]
    format_row(exp_table.rows[0], "111617", RGBColor(0xFF, 0xFF, 0xFF), bold=True, font_size=9.5)
    
    exp_data = [
        ("Pitch Micro-Jitter (%)", "Percentage (0.0% – 5.0%+)", "Natural human vocal cords exhibit natural micro-variations (jitter ~0.5%–1.8%). Neural TTS models frequently produce unnaturally rigid, flat pitch periods (jitter < 0.2%) or synthetic jitter spikes."),
        ("Spectral Discontinuity", "Normalized Index (0.0 – 1.0)", "Measures unnatural boundary jumps between consecutive spectral frames, revealing concatenation seams or vocoder artifacts."),
        ("Diagnostic Reasons List", "Array of Plain-Text Findings", "Human-readable explanations (e.g., 'Elevated urgency language detected', 'Acoustic feature anomaly exceeds threshold', 'Unnatural pitch consistency detected').")
    ]
    for m, s, i in exp_data:
        row = exp_table.add_row()
        for idx, width in enumerate(col_w_exp):
            row.cells[idx].width = width
        row.cells[0].paragraphs[0].add_run(m)
        row.cells[1].paragraphs[0].add_run(s)
        row.cells[2].paragraphs[0].add_run(i)
        format_row(row, "FFFFFF", RGBColor(0x2D, 0x37, 0x48), bold=False, font_size=9)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(16)
    
    # Section 9: Frontend Architecture & Motion Design
    h1 = doc.add_heading("9. Frontend User Experience & Motion Architecture", level=1)
    h1.runs[0].font.name = "Segoe UI Semibold"
    h1.runs[0].font.color.rgb = RGBColor(0x11, 0x16, 0x17)
    
    p = doc.add_paragraph(
        "VoiceGuard's user interface is designed with state-of-the-art visual aesthetics, dark glassmorphic styling, "
        "and purposeful micro-animations that communicate security state without causing cognitive overload. "
        "Key interface features include:"
    )
    p.runs[0].font.name = "Segoe UI"
    p.runs[0].font.size = Pt(10)
    
    fe_bullets = [
        ("Compact Navigation Rail with Animated Active Pill: ", "Desktop navigation collapses into an icon rail on tablet and fixed bottom navigation on mobile. Navigation tabs use Motion's layoutId='rail-active' to glide the glowing active indicator smoothly between pages."),
        ("Contextual Actions Stepper: ", "A 4-step pipeline header (01 Record → 02 Analyze → 03 Review → 04 Verify) tracks the exact state of the workflow and updates the primary CTA button contextually."),
        ("Concentric Multi-Track Radial Risk Gauge: ", "An SVG radial gauge that animates the combined risk index alongside concentric inner arcs representing acoustic (mint), linguistic (slate), and context (gold) contributions."),
        ("Interactive Signal Fusion Diagram: ", "Clickable input nodes (Acoustic, Linguistic, Context) connected via animated SVG bezier paths to the final score readout, allowing analysts to inspect the exact math behind the score."),
        ("Real-time AudioScope: ", "Microphone recording uses HTML5 Canvas and Web Audio API AnalyserNode to render 48 live frequency bars reflecting true speech amplitude."),
        ("Automated Product Showcase Carousel: ", "Landing page carousel that cycles automatically every 3.6s across 01 / Analyze, 02 / Understand, and 03 / Verify with an animated progress bar and glowing dynamic voice waveforms.")
    ]
    for fe1, fe2 in fe_bullets:
        bp = doc.add_paragraph(style='List Bullet')
        bp.paragraph_format.space_after = Pt(3)
        r1 = bp.add_run(fe1)
        r1.bold = True
        r1.font.name = "Segoe UI"
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(0x1B, 0x4D, 0x3E)
        r2 = bp.add_run(fe2)
        r2.font.name = "Segoe UI"
        r2.font.size = Pt(9.5)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(16)
    
    # Section 10: Running and Testing
    h1 = doc.add_heading("10. Deployment & Execution Instructions", level=1)
    h1.runs[0].font.name = "Segoe UI Semibold"
    h1.runs[0].font.color.rgb = RGBColor(0x11, 0x16, 0x17)
    
    p = doc.add_paragraph(
        "To run the complete VoiceGuard full-stack application locally:\n\n"
        "1. Backend Service (FastAPI):\n"
        "   cd backend\n"
        "   .venv\\Scripts\\uvicorn app.main:app --reload --port 8000\n\n"
        "2. Frontend Web Application (Vite):\n"
        "   cd frontend\n"
        "   npm run dev\n\n"
        "3. Automated Testing:\n"
        "   cd backend\n"
        "   .venv\\Scripts\\python -c \"import tests.test_contract as t; t.test_health(); t.test_fusion_thresholds(); t.test_linguistic_multilingual(); t.test_explainability_forensics(); print('Contract tests passed!')\""
    )
    p.runs[0].font.name = "Consolas"
    p.runs[0].font.size = Pt(9)
    p.runs[0].font.color.rgb = RGBColor(0x1A, 0x20, 0x2C)
    
    doc.add_paragraph().paragraph_format.space_after = Pt(18)
    
    # Final Signoff
    footer_p = doc.add_paragraph()
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    frun = footer_p.add_run("— End of VoiceGuard Platform Documentation —")
    frun.font.name = "Segoe UI"
    frun.font.size = Pt(9)
    frun.italic = True
    frun.font.color.rgb = RGBColor(0x71, 0x80, 0x96)
    
    target_path = Path(r"c:\Users\kavit\voice-guard\VoiceGuard_Complete_Project_Documentation.docx")
    doc.save(str(target_path))
    print(f"Document successfully created at: {target_path}")

if __name__ == "__main__":
    create_document()

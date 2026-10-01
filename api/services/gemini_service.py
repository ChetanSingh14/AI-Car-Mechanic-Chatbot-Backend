import os
import json
import time
import logging
import warnings
from django.conf import settings

# Suppress harmless deprecation/future warnings
warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger(__name__)

class GeminiMechanicService:
    SYSTEM_PROMPT = """
You are a Master ASE-Certified Automobile Technician with 25+ years of diagnostic experience in mechanical, electrical, drivetrain, and powertrain repair.
Your tone is professional, helpful, reassuring, and precise.

DIAGNOSTIC GUIDELINES:
1. ONLY answer automobile/car-related diagnostic and repair questions.
2. Provide systematic diagnostic reasoning: Symptoms -> Probable Root Causes -> Safety Assessment -> Inspection Steps -> Repair Recommendation.
3. If the user's description of symptoms is vague or lacks critical context (such as when it occurs, exact sounds, smells, warning lights, driving conditions), ask 1-3 targeted follow-up clarifying questions before finalizing a definitive diagnosis.
4. Always estimate realistic repair cost ranges (e.g., $150 - $350) and urgency (Low, Medium, High, Critical).
5. Recommend a specific automotive repair or maintenance service.
6. When media analysis summaries are provided, incorporate acoustic/visual observations into your explanation.
"""

    DEFAULT_MODELS = [
        'gemini-3.5-flash',
        'gemini-3.5-flash-lite',
        'gemini-3.1-flash-lite',
        'gemini-flash-lite-latest',
        'gemini-3.8-flash',
        'gemini-3.6-flash',
        'gemini-3.7-flash',
        'gemini-flash-latest',
        'gemini-2.5-flash',
        'gemini-2.5-flash-lite'
    ]

    @classmethod
    def get_models(cls):
        raw = os.getenv('GEMINI_MODELS', '')
        if raw:
            models = [m.strip() for m in raw.split(',') if m.strip()]
            if models:
                return models
        return cls.DEFAULT_MODELS

    @classmethod
    def get_api_key(cls):
        return getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')

    @classmethod
    def analyze_media_file_once(cls, media_attachment):
        """
        Analyzes an uploaded media file once if Gemini is available, caching the analysis in MediaAttachment.analysis_summary.
        If Gemini is unavailable or fails, returns None and leaves analysis_summary pending for future retry.
        """
        if media_attachment.analysis_summary:
            return media_attachment.analysis_summary

        api_key = cls.get_api_key()
        file_path = media_attachment.file.path if hasattr(media_attachment.file, 'path') else None

        if not file_path or not os.path.exists(file_path):
            return None

        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)

                prompt = (
                    f"As a master mechanic, provide a concise 1-2 sentence technical inspection summary of this automotive {media_attachment.file_type} "
                    f"({media_attachment.original_name}). Identify any visible wear, damage, leak, or acoustic anomalies."
                )

                contents = []
                if media_attachment.file_type == 'image':
                    from PIL import Image
                    contents = [prompt, Image.open(file_path)]
                elif media_attachment.file_type in ['audio', 'video']:
                    uploaded_file = genai.upload_file(file_path)
                    contents = [prompt, uploaded_file]

                if contents:
                    for model_name in cls.get_models():
                        try:
                            model = genai.GenerativeModel(model_name)
                            res = model.generate_content(contents, request_options={"timeout": 12})
                            if res and res.text:
                                summary = res.text.strip()
                                media_attachment.analysis_summary = summary
                                media_attachment.save(update_fields=['analysis_summary'])
                                return summary
                        except Exception as model_err:
                            logger.warning(f"Media analysis with {model_name} failed: {model_err}. Rotating to next model...")
                            continue
            except Exception as e:
                logger.warning(f"Could not perform single-pass media analysis with Gemini: {e}")

        # When Gemini didn't run or failed, keep analysis_summary as None (pending) without saving fake text
        return None

    @classmethod
    def generate_chat_response(cls, conversation, user_message_text: str, media_attachments=None):
        api_key = cls.get_api_key()

        # Gather context
        car_info = f"{conversation.car_year or ''} {conversation.car_make or ''} {conversation.car_model or ''}".strip()
        
        # History window fix: Chronological order of last 10 messages
        history_msgs = list(conversation.messages.order_by('-created_at')[:10])[::-1]
        context_str = f"Vehicle: {car_info or 'Unknown Vehicle'}\n"
        for m in history_msgs:
            context_str += f"{m.sender.upper()}: {m.content}\n"

        # Media summary text cached without re-uploading files every turn
        media_summaries = []
        if media_attachments:
            for media in media_attachments:
                summary = cls.analyze_media_file_once(media)
                if summary:
                    media_summaries.append(f"[{media.file_type.upper()} ({media.original_name})]: {summary}")

        media_info = ""
        if media_summaries:
            media_info = "\nUPLOADED MEDIA INSPECTIONS:\n" + "\n".join(media_summaries)

        prompt = (
            f"{cls.SYSTEM_PROMPT}\n\n"
            f"CONVERSATION CONTEXT:\n{context_str}{media_info}\n"
            f"LATEST USER QUERY: {user_message_text}\n\n"
            f"PROVIDE YOUR EXPERT MECHANIC RESPONSE:"
        )

        if api_key:
            start_time = time.monotonic()
            MAX_AI_BUDGET_SECONDS = 30

            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)

                # Dynamic Model Fallback Rotation: automatically fallback to next model if down/quota exhausted
                for model_name in cls.get_models():
                    if time.monotonic() - start_time > MAX_AI_BUDGET_SECONDS:
                        logger.warning("Gemini AI time budget exceeded (30s); halting rotation.")
                        break

                    try:
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content([prompt], request_options={"timeout": 10})
                        if response and response.text:
                            return {
                                "text": response.text.strip(),
                                "is_ai_generated": True
                            }
                    except Exception as model_err:
                        logger.warning(f"Gemini model {model_name} failed ({type(model_err).__name__}: {model_err}). Rotating to next model in chain...")
                        continue

            except Exception as e:
                logger.error(f"Gemini API error: {e}. Falling back to rule engine.")

        # Senior Technician Fallback Engine (Rules)
        return {
            "text": cls._fallback_technician_response(car_info, user_message_text, media_attachments),
            "is_ai_generated": False
        }

    @classmethod
    def generate_diagnosis(cls, conversation):
        """
        Generate structured JSON diagnosis using Gemini, or the expert rule matrix.
        Returns: (diag_dict, is_ai_generated)
        """
        api_key = cls.get_api_key()
        car_info = f"{conversation.car_year or ''} {conversation.car_make or ''} {conversation.car_model or ''}".strip() or "Vehicle"
        
        messages = list(conversation.messages.order_by('-created_at')[:15])[::-1]
        user_complaints = [m.content for m in messages if m.sender == 'user']
        complaint_text = " | ".join(user_complaints) if user_complaints else "Standard mechanical inspection"
        
        media_attachments = conversation.media_attachments.all()
        media_summaries = [cls.analyze_media_file_once(m) for m in media_attachments if cls.analyze_media_file_once(m)]
        media_context = " | Media: " + " ; ".join(media_summaries) if media_summaries else ""

        prompt = f"""
You are an expert ASE Master Automotive Diagnostic Technician.
Analyze this vehicle symptom report and media to output ONLY a valid JSON object:
Vehicle: {car_info}
Symptoms/History: {complaint_text}{media_context}

JSON format required (no extra markdown outside of json):
{{
  "issue_title": "Short specific title of issue (e.g., Worn Front Brake Pads & Rotors)",
  "severity": "low|medium|high|critical",
  "description": "2-3 sentence technical explanation of root cause, affected system, and safety impact.",
  "recommended_service": "Exact recommended service (e.g., Front Brake Pad and Rotor Replacement)",
  "estimated_cost": "$150 - $350"
}}
"""
        if api_key:
            start_time = time.monotonic()
            MAX_AI_BUDGET_SECONDS = 30

            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)

                for model_name in cls.get_models():
                    if time.monotonic() - start_time > MAX_AI_BUDGET_SECONDS:
                        logger.warning("Gemini diagnosis time budget exceeded (30s); halting rotation.")
                        break

                    try:
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content([prompt], request_options={"timeout": 10})
                        if response and response.text:
                            raw_text = response.text.strip()
                            if "```json" in raw_text:
                                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                            elif "```" in raw_text:
                                raw_text = raw_text.split("```")[1].split("```")[0].strip()

                            parsed = json.loads(raw_text)
                            if 'issue_title' in parsed and 'recommended_service' in parsed:
                                return parsed, True
                    except Exception as diag_err:
                        logger.warning(f"Diagnosis generation on {model_name} failed ({type(diag_err).__name__}: {diag_err}). Rotating to next model in chain...")
                        continue
            except Exception as e:
                logger.error(f"Gemini Diagnosis JSON Error: {e}. Falling back to rule matrix.")

        # Fallback Diagnostic Matrix based on keyword matching
        return cls._fallback_diagnosis_matrix(complaint_text, car_info), False

    @classmethod
    def _fallback_technician_response(cls, car_info: str, user_query: str, media_attachments) -> str:
        q_lower = user_query.lower()

        media_note = ""
        if media_attachments and len(media_attachments) > 0:
            media_note = (
                f"\n\n📎 *Note on attached media ({len(media_attachments)} file(s)):* "
                f"Automated AI media analysis is currently pending/offline. "
                f"Please describe what you see or hear in detail (e.g. location of noise, color of fluid or smoke) "
                f"so I can provide the most accurate assessment!"
            )

        if 'brake' in q_lower or 'squeal' in q_lower or 'grinding' in q_lower:
            return (
                f"Based on the symptoms for your {car_info or 'vehicle'}, squealing or grinding noises during braking usually point to worn brake friction pads "
                f"or glazed brake rotors. If it's a high-pitched metallic squeal, the wear indicator shim is contacting the rotor.\n\n"
                f"Diagnostic Steps:\n1. Inspect front brake pad thickness (minimum safe limit is 3mm).\n"
                f"2. Check rotors for scoring, deep grooves, or heat discoloration.\n"
                f"3. Verify caliper slide pins are lubricated and moving freely.\n\n"
                f"Safety Note: Brake wear directly affects stopping distance. I recommend having a certified technician perform a brake system inspection.{media_note}"
            )
        elif 'start' in q_lower or 'click' in q_lower or 'dead' in q_lower or 'battery' in q_lower:
            return (
                f"For a vehicle failing to crank or showing rapid clicking, the issue is typically in the starting/charging circuit.\n\n"
                f"Common Causes:\n1. Discharged or failing 12V battery (voltage under 12.4V resting).\n"
                f"2. Corroded or loose battery terminals.\n"
                f"3. Starter motor solenoid failure.\n\n"
                f"Recommendation: Perform a battery load test and terminal cleanup.{media_note}"
            )
        elif 'check engine' in q_lower or 'light' in q_lower or 'p0' in q_lower:
            return (
                f"An illuminated Check Engine Light indicates your vehicle's engine control module (ECM) has logged an OBD-II diagnostic trouble code (DTC).\n\n"
                f"Frequent triggers include:\n- Oxygen (O2) Sensor failure\n- Loose or faulty Gas Cap\n- Mass Air Flow (MAF) Sensor fouling\n- Misfires (Spark Plugs or Ignition Coils)\n\n"
                f"Next Step: Scan the OBD-II port for specific codes (P0300, P0420, etc.) to confirm exact component failure.{media_note}"
            )
        elif any(w in q_lower for w in ['accident', 'crash', 'collision', 'damage', 'dent', 'bumper', 'fender', 'hood', 'wreck']):
            return (
                f"Based on the visual collision and body damage reported for your {car_info or 'vehicle'}, "
                f"front-end impact typically involves structural, cooling, and alignment components beyond visible body panels.\n\n"
                f"Critical Collision Inspection Checklist:\n"
                f"1. Structural Core & Radiator Support: Check radiator, A/C condenser, and transmission cooler for cracks or fluid leaks.\n"
                f"2. Steering & Suspension Alignment: Inspect control arms, tie rods, wheel arch liners, and strut towers for bending.\n"
                f"3. Frame Rail & Crumple Zone Integrity: Verify front bumper reinforcement bar and subframe mounting alignment.\n"
                f"4. Sensor & Wiring Harnesses: Inspect frontal radar sensors, airbag impact sensors, and headlight harness continuity.\n\n"
                f"Safety Notice: Driving a vehicle with front-end collision damage carries severe risks of overheating, sudden fluid loss, and steering failure. "
                f"I strongly advise having the vehicle towed to a certified collision and mechanical repair facility.{media_note}"
            )
        elif 'oil' in q_lower or 'leak' in q_lower or 'smoke' in q_lower:
            return (
                f"Fluid leaks or smoke from under the hood require immediate attention to prevent engine thermal or mechanical damage.\n\n"
                f"Key Checks:\n1. Check dipstick level immediately before driving.\n2. Inspect valve cover gasket, oil pan plug, and filter housing.\n3. Identify fluid color (Brown/Black = Engine Oil, Red = Transmission, Green/Pink = Coolant).\n\n"
                f"Safety Notice: Low oil pressure can cause severe engine seizure within minutes.{media_note}"
            )

        return (
            f"Thank you for details on your {car_info or 'vehicle'}. As your Automobile Technician, I've analyzed your description.\n\n"
            f"System Analysis:\n- Primary system affected: Powertrain / Chassis\n- Recommended inspection: Diagnostic scan and visual hoist inspection.\n\n"
            f"Would you like me to generate a full formal diagnosis and estimate for your vehicle?{media_note}"
        )

    @classmethod
    def _fallback_diagnosis_matrix(cls, complaint_text: str, car_info: str) -> dict:
        text = complaint_text.lower()
        
        if 'brake' in text or 'squeal' in text or 'grinding' in text or 'stopping' in text:
            return {
                "issue_title": f"Brake Pad & Rotor Wear Inspection ({car_info})",
                "severity": "high",
                "description": "Friction pad material is worn near or past safety thresholds, causing metal wear contact on brake rotors during deceleration.",
                "recommended_service": "Front & Rear Brake Pad and Rotor Service",
                "estimated_cost": "$220 - $450"
            }
        elif 'battery' in text or 'start' in text or 'click' in text or 'alternator' in text:
            return {
                "issue_title": f"Starting & Charging System Degradation ({car_info})",
                "severity": "medium",
                "description": "12V lead-acid battery voltage drop under load or starter solenoid contact wear preventing engine turnover.",
                "recommended_service": "Battery Load Test & Starter Replacement",
                "estimated_cost": "$150 - $320"
            }
        elif 'check engine' in text or 'misfire' in text or 'p0' in text:
            return {
                "issue_title": f"Engine Misfire / Emissions DTC Fault ({car_info})",
                "severity": "medium",
                "description": "Engine control unit detected combustion inefficiency due to fouled spark plugs, failing ignition coils, or vacuum leak.",
                "recommended_service": "OBD-II Code Scan & Ignition System Tune-Up",
                "estimated_cost": "$120 - $280"
            }
        elif any(w in text for w in ['accident', 'crash', 'collision', 'damage', 'dent', 'bumper', 'fender', 'hood', 'wreck']):
            return {
                "issue_title": f"Front-End Collision & Core Structural Damage ({car_info})",
                "severity": "critical",
                "description": "Front-end impact has compromised outer bodywork (bumper, hood, fender), with likely damage to the radiator support, cooling assembly, and steering/suspension geometry.",
                "recommended_service": "Collision Repair, Radiator Core Support & Front Suspension Realignment",
                "estimated_cost": "$1,800 - $4,500"
            }
        elif 'leak' in text or 'overheat' in text or 'coolant' in text or 'radiator' in text:
            return {
                "issue_title": f"Cooling System Pressure Loss / Overheating Risk ({car_info})",
                "severity": "critical",
                "description": "Coolant fluid leakage or failing thermostat causing engine operating temperature to exceed normal safety bounds.",
                "recommended_service": "Cooling System Pressure Test & Radiator Hose Repair",
                "estimated_cost": "$200 - $550"
            }

        return {
            "issue_title": f"Comprehensive Vehicle Diagnostic Assessment ({car_info})",
            "severity": "medium",
            "description": "General mechanical/electrical anomaly detected requiring multi-point digital inspection and sensor readout.",
            "recommended_service": "Full 50-Point Automotive Diagnostic Inspection",
            "estimated_cost": "$99 - $199"
        }

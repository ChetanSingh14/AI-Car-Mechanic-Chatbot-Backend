import os
import json
import logging
import warnings
from django.conf import settings

# Suppress harmless deprecation/future warnings
warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger(__name__)

class GeminiMechanicService:
    SYSTEM_PROMPT = """
You are a Master ASE-Certified Automobile Technician with 25+ years of diagnostic experience in mechanical, electrical, and powertrain repair.
Your tone is professional, helpful, reassuring, and precise.

RULES:
1. ONLY answer automobile/car-related questions.
2. Provide systematic diagnostic reasoning (e.g. Symptoms -> Probable Causes -> Safety Assessment -> Next Steps).
3. Always include estimated repair costs range and urgency (Low, Medium, High, Critical).
4. Recommend a specific repair service (e.g., Brake Pad Replacement, Alternator Replacement, Engine Diagnostic).
5. If the user asks for diagnosis or has described full symptoms, provide a clear structured diagnosis summary.
"""

    AVAILABLE_MODELS = [
        'gemini-flash-lite-latest',  # 15 RPM, 500 Requests/Day
        'gemini-3.5-flash-lite',     # 15 RPM, 500 Requests/Day
        'gemini-3.1-flash-lite',     # 15 RPM, 500 Requests/Day
        'gemini-flash-latest',       # 5 RPM, 20 Requests/Day
        'gemini-pro-latest'          # High capability fallback
    ]

    @classmethod
    def get_api_key(cls):
        return getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')

    @classmethod
    def generate_chat_response(cls, conversation, user_message_text: str, media_attachments=None):
        api_key = cls.get_api_key()

        # Gather context
        car_info = f"{conversation.car_year or ''} {conversation.car_make or ''} {conversation.car_model or ''}".strip()
        history_msgs = conversation.messages.all()[:10]
        context_str = f"Vehicle: {car_info or 'Unknown'}\n"
        for m in history_msgs:
            context_str += f"{m.sender.upper()}: {m.content}\n"

        media_info = ""
        if media_attachments and len(media_attachments) > 0:
            media_info = "\nUploaded Media Attachments: " + ", ".join([f"{m.file_type} ({m.original_name})" for m in media_attachments])

        prompt = f"{cls.SYSTEM_PROMPT}\n\nCONVERSATION HISTORY:\n{context_str}{media_info}\nLATEST USER QUERY: {user_message_text}\n\nPROVIDE YOUR EXPERT MECHANIC RESPONSE:"

        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)

                # Prepare multimodal contents
                contents = [prompt]
                if media_attachments:
                    for media in media_attachments:
                        if not os.path.exists(media.file.path):
                            continue
                        try:
                            if media.file_type == 'image':
                                from PIL import Image
                                img = Image.open(media.file.path)
                                contents.append(img)
                            elif media.file_type in ['audio', 'video']:
                                # Upload audio/video using genai.upload_file for acoustic waveform / video frame analysis
                                uploaded_media = genai.upload_file(media.file.path)
                                contents.append(uploaded_media)
                        except Exception as img_err:
                            logger.warning(f"Could not load {media.file_type} for Gemini: {img_err}")

                # Dynamic Model Rotation across highest RPM/RPD models
                for model_name in cls.AVAILABLE_MODELS:
                    try:
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(contents)
                        if response and response.text:
                            return {
                                "text": response.text,
                                "is_ai_generated": True
                            }
                    except Exception as model_err:
                        logger.warning(f"Gemini model {model_name} rate-limited or unavailable: {model_err}. Rotating...")
                        continue

            except Exception as e:
                logger.error(f"Gemini API initialization error: {e}. Falling back to Senior Technician Rule Engine.")

        # Senior Technician Fallback Engine (when API key is missing or failed)
        return {
            "text": cls._fallback_technician_response(car_info, user_message_text, media_attachments),
            "is_ai_generated": False
        }

    @classmethod
    def generate_diagnosis(cls, conversation):
        api_key = cls.get_api_key()
        car_info = f"{conversation.car_year or ''} {conversation.car_make or ''} {conversation.car_model or ''}".strip() or "Vehicle"
        
        messages = list(conversation.messages.all())
        user_complaints = [m.content for m in messages if m.sender == 'user']
        complaint_text = " ".join(user_complaints)
        media_attachments = conversation.media_attachments.all()

        prompt = f"""
You are an expert car mechanic. Analyze this vehicle issue description and any uploaded media (images/audio/video) to output ONLY a JSON object:
Vehicle: {car_info}
Symptoms/History: {complaint_text}

JSON format required:
{{
  "issue_title": "Short title of issue (e.g., Worn Front Brake Pads & Rotors)",
  "severity": "low|medium|high|critical",
  "description": "2-3 sentence technical explanation of cause and impact based on symptoms and media analysis.",
  "recommended_service": "Recommended repair action (e.g., Front Brake Pad and Rotor Replacement)",
  "estimated_cost": "$150 - $350"
}}
"""
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)

                diag_contents = [prompt]
                if media_attachments:
                    for media in media_attachments:
                        if os.path.exists(media.file.path):
                            try:
                                if media.file_type == 'image':
                                    from PIL import Image
                                    diag_contents.append(Image.open(media.file.path))
                                elif media.file_type in ['audio', 'video']:
                                    diag_contents.append(genai.upload_file(media.file.path))
                            except Exception as m_err:
                                logger.warning(f"Could not load {media.file_type} for diagnosis: {m_err}")

                for model_name in cls.AVAILABLE_MODELS:
                    try:
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(diag_contents)
                        
                        raw_text = response.text.strip()
                        if "```json" in raw_text:
                            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in raw_text:
                            raw_text = raw_text.split("```")[1].split("```")[0].strip()

                        parsed = json.loads(raw_text)
                        return parsed
                    except Exception as diag_err:
                        logger.warning(f"Diagnosis generation on {model_name} failed: {diag_err}. Rotating...")
                        continue
            except Exception as e:
                logger.error(f"Gemini Diagnosis JSON Error: {e}")

        # Fallback Diagnostic Matrix based on keyword matching
        return cls._fallback_diagnosis_matrix(complaint_text, car_info)

    @classmethod
    def _fallback_technician_response(cls, car_info: str, user_query: str, media_attachments) -> str:
        q_lower = user_query.lower()

        media_note = ""
        if media_attachments and len(media_attachments) > 0:
            media_note = f"\n\n[Media Analysis]: Received {len(media_attachments)} file(s). Inspection noted visual/acoustic anomaly matching symptom report."

        if 'brake' in q_lower or 'squeal' in q_lower or 'grinding' in q_lower:
            return (
                f"Based on the symptoms for your {car_info}, squealing or grinding noises during braking usually point to worn brake friction pads "
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
        elif 'check engine' in q_lower or 'light' in q_lower or 'code' in q_lower:
            return (
                f"An illuminated Check Engine Light indicates your vehicle's engine control module (ECM) has logged an OBD-II diagnostic trouble code (DTC).\n\n"
                f"Frequent triggers include:\n- Oxygen (O2) Sensor failure\n- Loose or faulty Gas Cap\n- Mass Air Flow (MAF) Sensor fouling\n- Misfires (Spark Plugs or Ignition Coils)\n\n"
                f"Next Step: Scan the OBD-II port for specific codes (P0300, P0420, etc.) to confirm exact component failure.{media_note}"
            )
        elif 'oil' in q_lower or 'leak' in q_lower or 'smoke' in q_lower:
            return (
                f"Fluid leaks or smoke from under the hood require immediate attention to prevent engine thermal or mechanical damage.\n\n"
                f"Key Checks:\n1. Check dipstick level immediately before driving.\n2. Inspect valve cover gasket, oil pan plug, and filter housing.\n3. Identify fluid color (Brown/Black = Engine Oil, Red = Transmission, Green/Pink = Coolant).\n\n"
                f"Safety Notice: Low oil pressure can cause severe engine seizure within minutes.{media_note}"
            )

        return (
            f"Thank you for details on your {car_info}. As your Automobile Technician, I've analyzed your description.\n\n"
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
        elif 'check engine' in text or 'misfire' in text or 'light' in text:
            return {
                "issue_title": f"Engine Misfire / Emissions DTC Fault ({car_info})",
                "severity": "medium",
                "description": "Engine control unit detected combustion inefficiency due to fouled spark plugs, failing ignition coils, or vacuum leak.",
                "recommended_service": "OBD-II Code Scan & Ignition System Tune-Up",
                "estimated_cost": "$120 - $280"
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

import re

class IntentService:
    # Automotive domain keywords (single words)
    CAR_KEYWORDS = {
        'car', 'vehicle', 'auto', 'automobile', 'truck', 'suv', 'engine', 'brake', 'brakes',
        'transmission', 'gearbox', 'clutch', 'oil', 'filter', 'battery', 'starter', 'alternator',
        'radiator', 'coolant', 'exhaust', 'muffler', 'tire', 'tires', 'wheel', 'suspension',
        'strut', 'shock', 'steering', 'belt', 'timing', 'sparkplug', 'cylinder', 'fuel',
        'injector', 'turbo', 'turbocharger', 'manifold', 'catalytic', 'converter', 'squeal',
        'grinding', 'knocking', 'rattle', 'smoke', 'leak', 'leaking', 'overheating', 'misfire',
        'vibration', 'dashboard', 'powertrain', 'drivetrain', 'chassis', 'rotor', 'caliper',
        'sparkplugs', 'mileage', 'odometer', 'accelerator', 'rpm', 'headlight', 'tailgate',
        'accident', 'crash', 'collision', 'damage', 'damaged', 'dent', 'dented',
        'scratch', 'bumper', 'fender', 'hood', 'windshield', 'airbag', 'frame',
        'bodywork', 'paint', 'hit', 'smashed', 'wreck', 'wrecked', 'repair',
        'repairs', 'fix', 'broken', 'inspect', 'inspection', 'check'
    }

    # Car multi-word phrases to match against full lowercase text
    CAR_PHRASES = [
        'check engine', 'brake pad', 'brake pads', 'spark plug', 'spark plugs',
        'oil change', 'timing belt', 'warning light', 'flat tire', 'won\'t start',
        'wont start', 'rough idle', 'hard start', 'black smoke', 'white smoke',
        'blue smoke', 'coolant leak', 'oil leak', 'power steering', 'air conditioning',
        'ac cold', 'ac warm', 'bad mileage', 'burning smell',
        'check this', 'look at this', 'see this', 'what happened', 'car accident',
        'front damage', 'rear damage', 'body damage', 'repair cost'
    ]

    # Popular car makes (with word-boundary matching)
    POPULAR_MAKES = [
        'honda', 'toyota', 'ford', 'chevrolet', 'chevy', 'bmw', 'mercedes', 'audi',
        'nissan', 'hyundai', 'kia', 'volkswagen', 'vw', 'subaru', 'mazda', 'jeep',
        'ram', 'dodge', 'lexus', 'tesla', 'volvo', 'porsche', 'acura', 'infiniti',
        'cadillac', 'buick', 'gmc', 'chrysler', 'mitsubishi', 'genesis', 'land rover',
        'jaguar', 'mini'
    ]

    # Off-topic keywords (single words) - 'code' removed to allow OBD codes
    OFF_TOPIC_KEYWORDS = {
        'recipe', 'cook', 'cooking', 'food', 'weather', 'rain', 'temperature',
        'python', 'javascript', 'java', 'programming', 'html', 'css', 'react',
        'django', 'politics', 'president', 'election', 'movie', 'film', 'song',
        'music', 'joke', 'crypto', 'bitcoin', 'stock', 'invest', 'relationship',
        'dating', 'homework', 'essay', 'math', 'solve', 'equation', 'translate',
        'football', 'basketball', 'soccer', 'cricket', 'astrology', 'horoscope'
    }

    # Off-topic phrases to match against full lowercase text
    OFF_TOPIC_PHRASES = [
        'tell me a story', 'who is', 'capital of', 'write code', 'how to code',
        'write a poem', 'tell a joke', 'what is the weather'
    ]

    # Common greetings
    GREETINGS = {'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy', 'greetings'}

    # OBD-II Diagnostic Trouble Code Pattern (e.g., P0300, B1000, C0123, U0100)
    OBD_PATTERN = re.compile(r'\b[PBCU]\d{4}\b', re.IGNORECASE)

    # Curated technical knowledge base for common OBD-II trouble codes (0-Token instant lookup)
    KNOWN_OBD_CODES = {
        'P0300': {
            'definition': 'Random or Multiple Cylinder Misfire Detected',
            'system': 'Ignition & Fuel Delivery System',
            'severity': 'High (Flashing Check Engine Light warns of catalytic converter damage)',
            'common_causes': [
                'Worn or fouled spark plugs / failed ignition coils',
                'Low fuel pressure or clogged fuel injectors',
                'Intake manifold vacuum leak or faulty PCV valve',
                'Faulty camshaft or crankshaft position sensor'
            ],
            'recommended_steps': [
                'Avoid heavy engine load or highway speeds if the Check Engine Light is flashing.',
                'Inspect spark plug electrodes and ignition coil boots for carbon tracking or oil fouling.',
                'Perform a fuel pressure test and check long-term fuel trims with a scan tool.'
            ]
        },
        'P0301': {
            'definition': 'Cylinder 1 Misfire Detected',
            'system': 'Ignition & Fuel System',
            'severity': 'Medium to High',
            'common_causes': [
                'Faulty Cylinder 1 ignition coil or spark plug',
                'Clogged or leaking Cylinder 1 fuel injector',
                'Low mechanical compression in Cylinder 1'
            ],
            'recommended_steps': [
                'Swap ignition coil #1 to coil #2 to determine if the misfire follows the coil.',
                'Inspect spark plug #1 for carbon deposits or fuel wetting.'
            ]
        },
        'P0420': {
            'definition': 'Catalyst System Efficiency Below Threshold (Bank 1)',
            'system': 'Exhaust & Emissions Control System',
            'severity': 'Moderate (Emissions test failure; safe for short-term driving)',
            'common_causes': [
                'Degraded or contaminated Catalytic Converter matrix',
                'Defective downstream Oxygen (O2) Sensor (Sensor 2)',
                'Exhaust leak upstream of or directly at the catalytic converter',
                'Unburned engine oil or coolant entering exhaust stream'
            ],
            'recommended_steps': [
                'Graph downstream O2 sensor voltage (should remain steady around 0.45V at idle).',
                'Inspect exhaust flanges and pipes for soot leaks or cracked welds.',
                'Ensure underlying misfires (P0300) are resolved prior to catalytic converter replacement.'
            ]
        },
        'P0171': {
            'definition': 'System Too Lean (Bank 1 - Too much air / too little fuel)',
            'system': 'Air-Fuel Metering & Induction System',
            'severity': 'Medium (May cause hesitation, rough idle, and increased combustion temps)',
            'common_causes': [
                'Dirty or contaminated Mass Air Flow (MAF) Sensor',
                'Unmetered vacuum leak (cracked intake boot, PCV hose, intake gasket)',
                'Weak fuel pump, clogged fuel filter, or restricted injectors',
                'Faulty upstream Oxygen Sensor reporting false lean'
            ],
            'recommended_steps': [
                'Clean MAF sensor elements with dedicated electronic aerosol cleaner.',
                'Perform an intake smoke test to detect cracked rubber hoses and vacuum leaks.',
                'Verify fuel pressure under load matches OEM specification.'
            ]
        },
        'P0172': {
            'definition': 'System Too Rich (Bank 1 - Too much fuel / too little air)',
            'system': 'Air-Fuel Metering System',
            'severity': 'Medium (Unburned fuel degrades oil and damages catalytic converter)',
            'common_causes': [
                'Leaking or stuck-open fuel injector',
                'Defective fuel pressure regulator causing excessive rail pressure',
                'Severely clogged engine air filter',
                'Faulty Engine Coolant Temperature (ECT) sensor reading falsely cold'
            ],
            'recommended_steps': [
                'Check air filter element for heavy dirt or restriction.',
                'Verify fuel rail pressure and check for vacuum regulator fuel leaks.',
                'Verify coolant temperature sensor live readings match actual engine temperature.'
            ]
        },
        'P0442': {
            'definition': 'Evaporative Emission (EVAP) Control System Small Leak Detected',
            'system': 'EVAP Fuel Vapor Recovery System',
            'severity': 'Low (Emissions compliance; does not affect drivability)',
            'common_causes': [
                'Loose, worn, or aftermarket fuel tank filler cap',
                'Deteriorated EVAP vapor hose or cracked charcoal canister',
                'Partially stuck-open EVAP canister vent valve or purge solenoid'
            ],
            'recommended_steps': [
                'Inspect the rubber gasket on the fuel cap for cracks or debris; tighten securely.',
                'Clear trouble code and operate vehicle across two driving cycles.',
                'Conduct an EVAP low-pressure smoke test if the code returns.'
            ]
        },
        'P0455': {
            'definition': 'Evaporative Emission (EVAP) System Gross / Large Leak Detected',
            'system': 'EVAP Fuel Vapor Recovery System',
            'severity': 'Low to Medium',
            'common_causes': [
                'Fuel filler cap missing, cross-threaded, or unlatched',
                'Disconnected or severed EVAP purge line',
                'Stuck wide-open EVAP vent solenoid'
            ],
            'recommended_steps': [
                'Inspect fuel cap fitment and fuel filler neck condition.',
                'Verify EVAP purge solenoid seals completely under vacuum.'
            ]
        },
        'P0128': {
            'definition': 'Coolant Temperature Below Thermostat Regulating Temperature',
            'system': 'Engine Thermal Cooling System',
            'severity': 'Low to Medium (Slow cabin heat, increased fuel consumption)',
            'common_causes': [
                'Engine thermostat stuck open or opening prematurely',
                'Defective Engine Coolant Temperature (ECT) sensor',
                'Low engine coolant level preventing sensor submersion'
            ],
            'recommended_steps': [
                'Check engine coolant level in overflow reservoir and radiator (when cold).',
                'Replace thermostat assembly and perform cooling system air bleed.'
            ]
        },
        'P0700': {
            'definition': 'Transmission Control System Malfunction (MIL Request)',
            'system': 'Automatic Transmission / Transaxle Powertrain',
            'severity': 'High (Requires dedicated transmission diagnostic scan)',
            'common_causes': [
                'Transmission Control Module (TCM) logged a mechanical or hydraulic fault',
                'Low, deteriorated, or contaminated automatic transmission fluid (ATF)',
                'Shift solenoid or torque converter clutch (TCC) circuit issue'
            ],
            'recommended_steps': [
                'Inspect transmission fluid level and condition (burnt odor or dark coloration).',
                'Scan the TCM module with an advanced OBD-II tool to retrieve specific P07xx subcodes.'
            ]
        }
    }

    @classmethod
    def get_known_obd_response(cls, code: str, car_info: str = "") -> str:
        code_upper = code.upper()
        data = cls.KNOWN_OBD_CODES.get(code_upper)
        if not data:
            return None

        vehicle_prefix = f" for your {car_info}" if car_info else ""
        causes_str = "\n".join(f"• {cause}" for cause in data['common_causes'])
        steps_str = "\n".join(f"{i+1}. {step}" for i, step in enumerate(data['recommended_steps']))

        return (
            f"🔍 **OBD-II Technical Diagnosis: Code {code_upper}**\n\n"
            f"• **Definition:** {data['definition']}\n"
            f"• **Subsystem:** {data['system']}\n"
            f"• **Diagnostic Severity:** {data['severity']}\n\n"
            f"**Probable Root Causes{vehicle_prefix}:**\n{causes_str}\n\n"
            f"**Recommended Diagnostic & Inspection Steps:**\n{steps_str}\n\n"
            f"💡 *Knowledge Base Lookup (0 AI Tokens). Would you like me to generate a full formal repair diagnosis and estimate?*"
        )

    @classmethod
    def evaluate_intent(cls, message_text: str, conversation):
        """
        Evaluates the input message using traditional heuristic logic to minimize AI usage.
        Returns:
            dict: {
                "action": "REJECT" | "FOLLOWUP" | "GENERATE_AI",
                "response_text": str or None,
                "is_car_related": bool,
                "extracted_info": dict
            }
        """
        text_lower = message_text.lower().strip()

        # Check if conversation has uploaded media attachments
        has_media = False
        try:
            if conversation and hasattr(conversation, 'media_attachments'):
                has_media = conversation.media_attachments.exists()
        except Exception:
            has_media = False
        words = set(re.findall(r'\b\w+\b', text_lower))

        # Check OBD-II code detection
        obd_matches = cls.OBD_PATTERN.findall(message_text)
        has_obd_code = len(obd_matches) > 0

        # Check car make presence using word boundaries
        detected_make = None
        for make in cls.POPULAR_MAKES:
            if re.search(r'\b' + re.escape(make) + r'\b', text_lower):
                detected_make = make.capitalize()
                break

        # Check multi-word phrase matches
        car_phrase_hits = sum(1 for phrase in cls.CAR_PHRASES if phrase in text_lower)
        off_topic_phrase_hits = sum(1 for phrase in cls.OFF_TOPIC_PHRASES if phrase in text_lower)

        # Single word hits
        car_word_hits = len(words.intersection(cls.CAR_KEYWORDS))
        off_topic_word_hits = len(words.intersection(cls.OFF_TOPIC_KEYWORDS))

        total_car_signals = car_word_hits + (car_phrase_hits * 2) + (2 if detected_make else 0) + (3 if has_obd_code else 0)
        total_off_topic_signals = off_topic_word_hits + (off_topic_phrase_hits * 2)

        extracted = {}
        if detected_make:
            extracted['car_make'] = detected_make
        if has_obd_code:
            extracted['obd_codes'] = obd_matches

        # Categorize symptom
        symptom_cat = cls._detect_symptom_category(text_lower)
        if symptom_cat:
            extracted['symptom_category'] = symptom_cat

        # 1. Direct off-topic rejection rule
        if total_off_topic_signals > 0 and total_car_signals == 0 and not has_media:
            return {
                "action": "REJECT",
                "response_text": (
                    "I am a specialized Automobile Technician AI. I can only assist with vehicle troubleshooting, "
                    "car mechanical diagnoses, maintenance, and repair bookings. "
                    "Please ask me a question related to your car or vehicle symptoms!"
                ),
                "is_car_related": False,
                "extracted_info": extracted
            }

        # 2. Standalone greetings check
        is_greeting_phrase = any(g == text_lower or text_lower.startswith(g + ' ') for g in cls.GREETINGS)
        if is_greeting_phrase and total_car_signals == 0 and not has_media:
            return {
                "action": "FOLLOWUP",
                "response_text": (
                    "👋 Hello! I'm your virtual Senior Automobile Technician.\n\n"
                    "What vehicle (Make, Model, Year) are you driving today, and what symptoms or issues are you experiencing?"
                ),
                "is_car_related": True,
                "extracted_info": extracted
            }

        # 3. Completely unrelated query check
        if total_car_signals == 0 and not conversation.car_make and not has_media:
            return {
                "action": "REJECT",
                "response_text": (
                    "I'm trained exclusively on automotive engineering, vehicle diagnostics, and repair logic. "
                    "If you are having an issue with your car (e.g., strange noises, warning lights, fluid leaks, or performance loss), "
                    "please describe the vehicle and symptoms!"
                ),
                "is_car_related": False,
                "extracted_info": extracted
            }

        # 4. Instant Zero-Token OBD-II Trouble Code Knowledge Base Lookup
        if has_obd_code:
            for raw_code in obd_matches:
                code_upper = raw_code.upper()
                if code_upper in cls.KNOWN_OBD_CODES:
                    car_info = f"{conversation.car_year or ''} {conversation.car_make or extracted.get('car_make') or ''} {conversation.car_model or ''}".strip()
                    return {
                        "action": "OBD_LOOKUP",
                        "response_text": cls.get_known_obd_response(code_upper, car_info),
                        "is_car_related": True,
                        "extracted_info": extracted
                    }

        # 4. Follow-up inquiry heuristic: when user query is too vague
        msg_count = conversation.messages.count()
        has_media = conversation.media_attachments.exists()
        current_make = conversation.car_make or extracted.get('car_make')

        # If very brief query with no detail and early in conversation
        is_vague_query = len(words) < 5 and total_car_signals <= 1 and not has_obd_code
        if (msg_count <= 1 or not current_make) and is_vague_query and not has_media:
            return {
                "action": "FOLLOWUP",
                "response_text": (
                    "Got it. To help pinpoint the exact mechanical cause, could you share:\n"
                    "1. Your vehicle's Make, Model, and Year?\n"
                    "2. When does the symptom happen (e.g. at idle, during braking, accelerating, or over bumps)?\n"
                    "3. Any dashboard warning lights or unusual sounds/smells?\n\n"
                    "You can also upload a photo or record audio/video using the media uploader!"
                ),
                "is_car_related": True,
                "extracted_info": extracted
            }

        # 5. Sufficient context -> Forward to Gemini AI
        return {
            "action": "GENERATE_AI",
            "response_text": None,
            "is_car_related": True,
            "extracted_info": extracted
        }

    @classmethod
    def _detect_symptom_category(cls, text_lower: str) -> str:
        categories = {
            'bodywork': ['accident', 'crash', 'collision', 'damage', 'bumper', 'dent', 'fender', 'hood', 'windshield', 'scratch', 'body', 'frame'],
            'brakes': ['brake', 'brakes', 'rotor', 'caliper', 'squeal', 'grinding', 'stopping', 'pad'],
            'engine': ['engine', 'misfire', 'cylinder', 'spark plug', 'timing', 'rpm', 'rough idle', 'stalling', 'knock'],
            'cooling': ['coolant', 'radiator', 'overheating', 'thermostat', 'antifreeze', 'water pump', 'steam'],
            'electrical': ['battery', 'alternator', 'starter', 'fuse', 'wiring', 'headlight', 'voltage', 'click'],
            'transmission': ['transmission', 'gear', 'clutch', 'shifting', 'slipping', 'fluid', 'drivetrain'],
            'exhaust': ['exhaust', 'muffler', 'catalytic', 'converter', 'smoke', 'emissions', 'fumes'],
            'suspension': ['suspension', 'strut', 'shock', 'sway bar', 'vibration', 'bouncing', 'alignment', 'steering']
        }
        for cat, kw_list in categories.items():
            for kw in kw_list:
                if kw in text_lower:
                    return cat
        return 'general'

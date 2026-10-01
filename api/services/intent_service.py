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
        'sparkplugs', 'mileage', 'odometer', 'accelerator', 'rpm', 'headlight', 'tailgate'
    }

    # Car multi-word phrases to match against full lowercase text
    CAR_PHRASES = [
        'check engine', 'brake pad', 'brake pads', 'spark plug', 'spark plugs',
        'oil change', 'timing belt', 'warning light', 'flat tire', 'won\'t start',
        'wont start', 'rough idle', 'hard start', 'black smoke', 'white smoke',
        'blue smoke', 'coolant leak', 'oil leak', 'power steering', 'air conditioning',
        'ac cold', 'ac warm', 'bad mileage', 'burning smell'
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
        if total_off_topic_signals > 0 and total_car_signals == 0:
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
        if is_greeting_phrase and total_car_signals == 0:
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
        if total_car_signals == 0 and not conversation.car_make:
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

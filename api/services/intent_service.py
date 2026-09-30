import re

class IntentService:
    # Automotive domain keywords
    CAR_KEYWORDS = {
        'car', 'vehicle', 'auto', 'automobile', 'truck', 'suv', 'engine', 'brake', 'brakes',
        'transmission', 'gear', 'clutch', 'oil', 'filter', 'battery', 'starter', 'alternator',
        'radiator', 'coolant', 'exhaust', 'muffler', 'tire', 'tires', 'wheel', 'suspension',
        'strut', 'shock', 'steering', 'belt', 'timing', 'spark', 'plug', 'cylinder', 'fuel',
        'pump', 'injector', 'turbo', 'manifold', 'catalytic', 'converter', 'squeal', 'grinding',
        'knocking', 'rattle', 'smoke', 'leak', 'leaking', 'overheating', 'misfire', 'vibration',
        'dashboard', 'light', 'check engine', 'abs', 'airbag', 'mileage', 'honda', 'toyota',
        'ford', 'chevrolet', 'bmw', 'mercedes', 'audi', 'nissan', 'hyundai', 'kia', 'volkswagen',
        'subaru', 'mazda', 'jeep', 'ram', 'dodge', 'lexus', 'tesla', 'volvo'
    }

    # Off-topic keywords
    OFF_TOPIC_KEYWORDS = {
        'recipe', 'cook', 'food', 'weather', 'rain', 'temperature', 'code', 'python', 'javascript',
        'java', 'programming', 'html', 'css', 'react', 'django', 'politics', 'president',
        'election', 'movie', 'film', 'song', 'music', 'joke', 'tell me a story', 'crypto',
        'bitcoin', 'stock', 'invest', 'relationship', 'dating', 'homework', 'essay', 'math',
        'solve', 'equation', 'who is', 'capital of', 'translate'
    }

    @classmethod
    def evaluate_intent(cls, message_text: str, conversation):
        """
        Evaluates the input message using traditional heuristic logic.
        Returns:
            dict: {
                "action": "REJECT" | "FOLLOWUP" | "GENERATE_AI",
                "response_text": str or None,
                "is_car_related": bool,
                "extracted_info": dict
            }
        """
        text_lower = message_text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))

        car_hits = len(words.intersection(cls.CAR_KEYWORDS))
        off_topic_hits = len(words.intersection(cls.OFF_TOPIC_KEYWORDS))

        # Direct off-topic rejection rule
        if off_topic_hits > 0 and car_hits == 0:
            return {
                "action": "REJECT",
                "response_text": (
                    "I am a specialized Automobile Technician AI. I can only assist with vehicle troubleshooting, "
                    "car mechanical diagnoses, maintenance, and repair bookings. "
                    "Please ask me a question related to your car or vehicle symptoms!"
                ),
                "is_car_related": False,
                "extracted_info": {}
            }

        # General non-car query check if message is short or clearly un-related
        if car_hits == 0 and not conversation.car_make and len(words) > 3:
            # Check for general greetings
            greetings = {'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'help'}
            if words.intersection(greetings):
                return {
                    "action": "FOLLOWUP",
                    "response_text": (
                        "Hello! I'm your virtual Senior Automobile Technician. "
                        "What vehicle (Make/Model/Year) are you driving today, and what symptoms or issues are you experiencing?"
                    ),
                    "is_car_related": True,
                    "extracted_info": {}
                }
            
            # If completely no car keywords in a full sentence
            return {
                "action": "REJECT",
                "response_text": (
                    "I'm trained exclusively on automotive engineering, vehicle diagnostics, and repair logic. "
                    "If you are having an issue with your car (e.g. strange noises, warning lights, leaks, or performance loss), "
                    "please describe the vehicle and symptoms!"
                ),
                "is_car_related": False,
                "extracted_info": {}
            }

        # Information Extraction heuristic
        extracted = {}
        # Simple make detection
        popular_makes = ['honda', 'toyota', 'ford', 'chevrolet', 'chevy', 'bmw', 'mercedes', 'audi', 'nissan', 'hyundai', 'kia', 'volkswagen', 'vw', 'subaru', 'mazda', 'jeep', 'dodge', 'lexus', 'tesla', 'volvo']
        for make in popular_makes:
            if make in text_lower:
                extracted['car_make'] = make.capitalize()
                break

        # Check turn count & missing metadata
        msg_count = conversation.messages.count()
        has_media = conversation.media_attachments.exists()

        if msg_count <= 2 and not conversation.car_make and not extracted.get('car_make') and not has_media:
            return {
                "action": "FOLLOWUP",
                "response_text": (
                    "Got it. To help pinpoint the exact mechanical cause, could you let me know: "
                    "\n1. Your vehicle's Make, Model, and Year?"
                    "\n2. When does the symptom occur (e.g., at idle, during braking, accelerating, or over bumps)?"
                    "\n\nYou can also upload an image, audio clip of the sound, or video using the media uploader!"
                ),
                "is_car_related": True,
                "extracted_info": extracted
            }

        # Otherwise, pass to Gemini for deep technical analysis & diagnosis
        return {
            "action": "GENERATE_AI",
            "response_text": None,
            "is_car_related": True,
            "extracted_info": extracted
        }

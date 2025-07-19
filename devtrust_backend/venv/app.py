# app.py
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore, auth
import json # Import json module
import traceback # Import traceback module for detailed error logging
# app.py
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore, auth
import json # Import json module
import traceback # Import traceback module for detailed error logging

# Load environment variables from .env file
load_dotenv()

# --- Firebase Admin SDK Initialization ---
# IMPORTANT: This path must match the JSON file you downloaded from Firebase.
# Ensure 'devtrustai-app-firebase-adminsdk-fbsvc-5ff75c5127.json' is in the same directory as app.py
SERVICE_ACCOUNT_KEY_PATH = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH', 'devtrustai-app-firebase-adminsdk-fbsvc-5ff75c5127.json')

try:
    # Initialize Firebase Admin SDK
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Admin SDK initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")
    print("Please ensure 'FIREBASE_SERVICE_KEY_PATH' in your .env file or the default path points to a valid Firebase service account key JSON file.")
    exit(1)

# --- Gemini API Configuration ---
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in environment variables. Please set it in a .env file.")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash') # Using gemini-1.5-flash for broader availability

app = Flask(__name__)
CORS(app) # Enable CORS for all origins for development. Restrict in production.

# Helper function to get the app_id (simulated for Canvas environment)
def get_app_id():
    # In a real deployment, you might get this from an environment variable
    # or a configuration file. For Canvas, it's __app_id.
    # For this backend, we'll use a placeholder or assume it's passed.
    return "devtrustai-app-id" # Placeholder app ID for Firestore path

# --- User Authentication and Profile Management ---

@app.route('/signup', methods=['POST'])
def signup():
    """Handles user registration."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    username = data.get('username')

    if not all([email, password, username]):
        return jsonify({"error": "Missing email, password, or username"}), 400

    try:
        # Create user with Firebase Authentication
        user = auth.create_user(email=email, password=password, display_name=username)
        user_id = user.uid

        # Create user profile in Firestore
        app_id = get_app_id()
        user_profile_ref = db.collection('artifacts').document(app_id).collection('users').document(user_id).collection('user_data').document('profile')
        user_profile_ref.set({
            'username': username,
            'email': email,
            'trust_score': 0, # Initial score
            'score_feedback': 'No score calculated yet.',
            'contribution_links': [],
            'certificates': [],
            'created_at': firestore.SERVER_TIMESTAMP
        })
        return jsonify({"message": "User created successfully", "userId": user_id}), 201
    except auth.EmailAlreadyExistsError:
        print(f"Signup error: Email already registered for {email}")
        return jsonify({"error": "Email already registered"}), 409
    except Exception as e:
        # Log the full exception for better debugging
        traceback.print_exc() # This will print the full traceback to your Flask terminal
        print(f"Signup error: {type(e).__name__}: {e}") # Print the type and message of the exception
        return jsonify({"error": "Failed to create user", "details": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    """
    Handles user login.
    Note: For security, direct password login should ideally be handled client-side
    with Firebase Client SDK, which then provides a token. This is a simplified
    backend example for demonstration.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({"error": "Missing email or password"}), 400

    try:
        # In a real app, you'd use Firebase Client SDK for login
        # and then verify the ID token on the backend.
        # For simplicity here, we'll just check if user exists.
        # This is NOT a secure way to handle login for production.
        user = auth.get_user_by_email(email)
        # For actual password verification, you'd need to use a client-side SDK
        # or a more advanced authentication flow.
        return jsonify({"message": "Login successful (backend check)", "userId": user.uid}), 200
    except auth.UserNotFoundError:
        return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"error": "Failed to login", "details": str(e)}), 500

@app.route('/get-user-profile/<user_id>', methods=['GET'])
def get_user_profile(user_id):
    """Retrieves user profile data from Firestore."""
    try:
        app_id = get_app_id()
        profile_ref = db.collection('artifacts').document(app_id).collection('users').document(user_id).collection('user_data').document('profile')
        profile_doc = profile_ref.get()

        if profile_doc.exists:
            return jsonify(profile_doc.to_dict()), 200
        else:
            return jsonify({"error": "User profile not found"}), 404
    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return jsonify({"error": "Failed to retrieve profile", "details": str(e)}), 500

# --- Chatbot Endpoint ---

@app.route('/chat', methods=['POST'])
def chat():
    """
    Handles chat requests, interacts with Gemini, and saves chat history.
    """
    data = request.get_json()
    user_prompt = data.get('prompt')
    user_id = data.get('userId') # Get user ID from frontend

    if not user_prompt:
        return jsonify({"error": "No prompt provided"}), 400
    if not user_id:
        return jsonify({"error": "User ID is required for chat history"}), 400

    try:
        app_id = get_app_id()
        chat_collection_ref = db.collection('artifacts').document(app_id).collection('users').document(user_id).collection('chat_history')

        # Save user message to Firestore
        chat_collection_ref.add({
            'sender': 'user',
            'text': user_prompt,
            'timestamp': firestore.SERVER_TIMESTAMP
        })

        # Generate content using the Gemini model
        # For a more context-aware chat, you could fetch recent history
        # and pass it to Gemini for conversational context.
        # For simplicity, we'll just send the current prompt.
        ai_response_text = ""
        try:
            # You can send a more specific prompt to Gemini to guide its answers
            # related to your website's content (DevTrust AI, methodology, etc.)
            # For example:
            # full_prompt = f"As DevTrust AI's assistant, answer this question about our platform: {user_prompt}"
            response = model.generate_content(user_prompt)
            if response and response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.text:
                                ai_response_text += part.text
                                break
                if not ai_response_text:
                    ai_response_text = "I couldn't generate a text response."
            else:
                ai_response_text = "I received an empty response from the AI."
        except Exception as gemini_e:
            print(f"Gemini API error: {gemini_e}")
            ai_response_text = "Sorry, I am having trouble processing your request with the AI. Please try again later."


        # Save bot response to Firestore
        chat_collection_ref.add({
            'sender': 'bot',
            'text': ai_response_text,
            'timestamp': firestore.SERVER_TIMESTAMP
        })

        return jsonify({"response": ai_response_text})

    except Exception as e:
        print(f"An error occurred in chat: {e}")
        return jsonify({"error": "An internal server error occurred.", "details": str(e)}), 500

@app.route('/get-chat-history/<user_id>', methods=['GET'])
def get_chat_history(user_id):
    """Retrieves chat history for a given user."""
    try:
        app_id = get_app_id()
        chat_collection_ref = db.collection('artifacts').document(app_id).collection('users').document(user_id).collection('chat_history')
        # Order by timestamp to get messages in chronological order
        query = chat_collection_ref.order_by('timestamp').stream()
        history = []
        for doc in query:
            history.append(doc.to_dict())
        return jsonify(history), 200
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        return jsonify({"error": "Failed to retrieve chat history", "details": str(e)}), 500

# --- Score Analysis Endpoint ---

@app.route('/calculate-score', methods=['POST'])
def calculate_score():
    """
    Calculates a DevTrust Score using Gemini and saves it to Firestore.
    This is a conceptual analysis; actual code/link parsing is complex.
    """
    data = request.get_json()
    user_id = data.get('userId')
    contribution_links = data.get('contributionLinks', [])
    certificates_text = data.get('certificatesText', '') # Assuming text content or descriptions

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    # Construct a prompt for Gemini based on the provided data
    analysis_prompt = f"""
    Analyze the following developer contributions and provide a "DevTrust Score" between 1 and 100,
    along with detailed feedback on Sentiment, Professionalism, Technical Expertise, and Collaboration.
    Also, suggest areas for improvement.

    Contribution Links:
    {', '.join(contribution_links) if contribution_links else 'No links provided.'}

    Certificate Information:
    {certificates_text if certificates_text else 'No certificate information provided.'}

    Based on this, generate a JSON response with the following structure:
    {{
        "score": <integer_score_1_to_100>,
        "summary": "<brief_summary_of_score>",
        "feedback": {{
            "technical_expertise": "<feedback>",
            "professionalism": "<feedback>",
            "collaboration": "<feedback>",
            "sentiment": "<feedback>"
        }},
        "improvements": "<suggestions_for_improvement>"
    }}
    """
    # Define the schema for the structured response
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "score": {"type": "INTEGER"},
            "summary": {"type": "STRING"},
            "feedback": {
                "type": "OBJECT",
                "properties": {
                    "technical_expertise": {"type": "STRING"},
                    "professionalism": {"type": "STRING"},
                    "collaboration": {"type": "STRING"},
                    "sentiment": {"type": "STRING"}
                }
            },
            "improvements": {"type": "STRING"}
        },
        "required": ["score", "summary", "feedback", "improvements"]
    }

    try:
        # Generate structured content using the Gemini model
        response = model.generate_content(
            analysis_prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=response_schema
            )
        )

        ai_analysis = response.text # This will be a JSON string
        parsed_analysis = json.loads(ai_analysis)

        score = parsed_analysis.get('score')
        summary = parsed_analysis.get('summary')
        feedback = parsed_analysis.get('feedback')
        improvements = parsed_analysis.get('improvements')

        # Save score and feedback to Firestore
        app_id = get_app_id()
        user_profile_ref = db.collection('artifacts').document(app_id).collection('users').document(user_id).collection('user_data').document('profile')
        user_profile_ref.set({ # Changed from .update to .set
            'trust_score': score,
            'score_feedback': {
                'summary': summary,
                'details': feedback,
                'improvements': improvements
            },
            'contribution_links': contribution_links, # Save links submitted
            # 'certificates': certificates_text, # Save certificate text/links if applicable
            'last_score_calculated_at': firestore.SERVER_TIMESTAMP
        }, merge=True) # Added merge=True

        return jsonify({
            "score": score,
            "summary": summary,
            "feedback": feedback,
            "improvements": improvements
        }), 200

    except Exception as e:
        # Print the full traceback to the Flask terminal for detailed debugging
        traceback.print_exc()
        print(f"Error calculating score: {type(e).__name__}: {e}")
        return jsonify({"error": "Failed to calculate score", "details": str(e)}), 500


# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# Load environment variables from .env file
load_dotenv()

# --- Firebase Admin SDK Initialization ---
# IMPORTANT: This path must match the JSON file you downloaded from Firebase.
# Ensure 'devtrustai-app-firebase-adminsdk-fbsvc-5ff75c5127.json' is in the same directory as app.py
SERVICE_ACCOUNT_KEY_PATH = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH', 'devtrustai-app-firebase-adminsdk-fbsvc-5ff75c5127.json')

try:
    # Initialize Firebase Admin SDK
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Admin SDK initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")
    print("Please ensure 'FIREBASE_SERVICE_KEY_PATH' in your .env file or the default path points to a valid Firebase service account key JSON file.")
    exit(1)

# --- Gemini API Configuration ---
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in environment variables. Please set it in a .env file.")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash') # Using gemini-1.5-flash for broader availability

app = Flask(__name__)
CORS(app) # Enable CORS for all origins for development. Restrict in production.

# Helper function to get the app_id (simulated for Canvas environment)
def get_app_id():
    # In a real deployment, you might get this from an environment variable
    # or a configuration file. For Canvas, it's __app_id.
    # For this backend, we'll use a placeholder or assume it's passed.
    return "devtrustai-app-id" # Placeholder app ID for Firestore path

# --- User Authentication and Profile Management ---

@app.route('/signup', methods=['POST'])
def signup():
    """Handles user registration."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    username = data.get('username')

    if not all([email, password, username]):
        return jsonify({"error": "Missing email, password, or username"}), 400

    try:
        # Create user with Firebase Authentication
        user = auth.create_user(email=email, password=password, display_name=username)
        user_id = user.uid

        # Create user profile in Firestore
        app_id = get_app_id()
        user_profile_ref = db.collection('artifacts').document(app_id).collection('users').document(user_id).collection('user_data').document('profile')
        user_profile_ref.set({
            'username': username,
            'email': email,
            'trust_score': 0, # Initial score
            'score_feedback': 'No score calculated yet.',
            'contribution_links': [],
            'certificates': [],
            'created_at': firestore.SERVER_TIMESTAMP
        })
        return jsonify({"message": "User created successfully", "userId": user_id}), 201
    except auth.EmailAlreadyExistsError:
        print(f"Signup error: Email already registered for {email}")
        return jsonify({"error": "Email already registered"}), 409
    except Exception as e:
        # Log the full exception for better debugging
        traceback.print_exc() # This will print the full traceback to your Flask terminal
        print(f"Signup error: {type(e).__name__}: {e}") # Print the type and message of the exception
        return jsonify({"error": "Failed to create user", "details": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    """
    Handles user login.
    Note: For security, direct password login should ideally be handled client-side
    with Firebase Client SDK, which then provides a token. This is a simplified
    backend example for demonstration.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({"error": "Missing email or password"}), 400

    try:
        # In a real app, you'd use Firebase Client SDK for login
        # and then verify the ID token on the backend.
        # For simplicity here, we'll just check if user exists.
        # This is NOT a secure way to handle login for production.
        user = auth.get_user_by_email(email)
        # For actual password verification, you'd need to use a client-side SDK
        # or a more advanced authentication flow.
        return jsonify({"message": "Login successful (backend check)", "userId": user.uid}), 200
    except auth.UserNotFoundError:
        return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"error": "Failed to login", "details": str(e)}), 500

@app.route('/get-user-profile/<user_id>', methods=['GET'])
def get_user_profile(user_id):
    """Retrieves user profile data from Firestore."""
    try:
        app_id = get_app_id()
        profile_ref = db.collection('artifacts').document(app_id).collection('users').document(user_id).collection('user_data').document('profile')
        profile_doc = profile_ref.get()

        if profile_doc.exists:
            return jsonify(profile_doc.to_dict()), 200
        else:
            return jsonify({"error": "User profile not found"}), 404
    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return jsonify({"error": "Failed to retrieve profile", "details": str(e)}), 500

# --- Chatbot Endpoint ---

@app.route('/chat', methods=['POST'])
def chat():
    """
    Handles chat requests, interacts with Gemini, and saves chat history.
    """
    data = request.get_json()
    user_prompt = data.get('prompt')
    user_id = data.get('userId') # Get user ID from frontend

    if not user_prompt:
        return jsonify({"error": "No prompt provided"}), 400
    if not user_id:
        return jsonify({"error": "User ID is required for chat history"}), 400

    try:
        app_id = get_app_id()
        chat_collection_ref = db.collection('artifacts').document(app_id).collection('users').document(user_id).collection('chat_history')

        # Save user message to Firestore
        chat_collection_ref.add({
            'sender': 'user',
            'text': user_prompt,
            'timestamp': firestore.SERVER_TIMESTAMP
        })

        # Generate content using the Gemini model
        # For a more context-aware chat, you could fetch recent history
        # and pass it to Gemini for conversational context.
        # For simplicity, we'll just send the current prompt.
        ai_response_text = ""
        try:
            # You can send a more specific prompt to Gemini to guide its answers
            # related to your website's content (DevTrust AI, methodology, etc.)
            # For example:
            # full_prompt = f"As DevTrust AI's assistant, answer this question about our platform: {user_prompt}"
            response = model.generate_content(user_prompt)
            if response and response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.text:
                                ai_response_text += part.text
                                break
                if not ai_response_text:
                    ai_response_text = "I couldn't generate a text response."
            else:
                ai_response_text = "I received an empty response from the AI."
        except Exception as gemini_e:
            print(f"Gemini API error: {gemini_e}")
            ai_response_text = "Sorry, I am having trouble processing your request with the AI. Please try again later."


        # Save bot response to Firestore
        chat_collection_ref.add({
            'sender': 'bot',
            'text': ai_response_text,
            'timestamp': firestore.SERVER_TIMESTAMP
        })

        return jsonify({"response": ai_response_text})

    except Exception as e:
        print(f"An error occurred in chat: {e}")
        return jsonify({"error": "An internal server error occurred.", "details": str(e)}), 500

@app.route('/get-chat-history/<user_id>', methods=['GET'])
def get_chat_history(user_id):
    """Retrieves chat history for a given user."""
    try:
        app_id = get_app_id()
        chat_collection_ref = db.collection('artifacts').document(app_id).collection('users').document(user_id).collection('chat_history')
        # Order by timestamp to get messages in chronological order
        query = chat_collection_ref.order_by('timestamp').stream()
        history = []
        for doc in query:
            history.append(doc.to_dict())
        return jsonify(history), 200
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        return jsonify({"error": "Failed to retrieve chat history", "details": str(e)}), 500

# --- Score Analysis Endpoint ---

@app.route('/calculate-score', methods=['POST'])
def calculate_score():
    """
    Calculates a DevTrust Score using Gemini and saves it to Firestore.
    This is a conceptual analysis; actual code/link parsing is complex.
    """
    data = request.get_json()
    user_id = data.get('userId')
    contribution_links = data.get('contributionLinks', [])
    certificates_text = data.get('certificatesText', '') # Assuming text content or descriptions

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    # Construct a prompt for Gemini based on the provided data
    analysis_prompt = f"""
    Analyze the following developer contributions and provide a "DevTrust Score" between 1 and 100,
    along with detailed feedback on Sentiment, Professionalism, Technical Expertise, and Collaboration.
    Also, suggest areas for improvement.

    Contribution Links:
    {', '.join(contribution_links) if contribution_links else 'No links provided.'}

    Certificate Information:
    {certificates_text if certificates_text else 'No certificate information provided.'}

    Based on this, generate a JSON response with the following structure:
    {{
        "score": <integer_score_1_to_100>,
        "summary": "<brief_summary_of_score>",
        "feedback": {{
            "technical_expertise": "<feedback>",
            "professionalism": "<feedback>",
            "collaboration": "<feedback>",
            "sentiment": "<feedback>"
        }},
        "improvements": "<suggestions_for_improvement>"
    }}
    """
    # Define the schema for the structured response
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "score": {"type": "INTEGER"},
            "summary": {"type": "STRING"},
            "feedback": {
                "type": "OBJECT",
                "properties": {
                    "technical_expertise": {"type": "STRING"},
                    "professionalism": {"type": "STRING"},
                    "collaboration": {"type": "STRING"},
                    "sentiment": {"type": "STRING"}
                }
            },
            "improvements": {"type": "STRING"}
        },
        "required": ["score", "summary", "feedback", "improvements"]
    }

    try:
        # Generate structured content using the Gemini model
        response = model.generate_content(
            analysis_prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=response_schema
            )
        )

        ai_analysis = response.text # This will be a JSON string
        import json
        parsed_analysis = json.loads(ai_analysis)

        score = parsed_analysis.get('score')
        summary = parsed_analysis.get('summary')
        feedback = parsed_analysis.get('feedback')
        improvements = parsed_analysis.get('improvements')

        # Save score and feedback to Firestore
        app_id = get_app_id()
        user_profile_ref = db.collection('artifacts').document(app_id).collection('users').document(user_id).collection('user_data').document('profile')
        user_profile_ref.update({
            'trust_score': score,
            'score_feedback': {
                'summary': summary,
                'details': feedback,
                'improvements': improvements
            },
            'contribution_links': contribution_links, # Save links submitted
            # 'certificates': certificates_text, # Save certificate text/links if applicable
            'last_score_calculated_at': firestore.SERVER_TIMESTAMP
        })

        return jsonify({
            "score": score,
            "summary": summary,
            "feedback": feedback,
            "improvements": improvements
        }), 200

    except Exception as e:
        # Print the full traceback to the Flask terminal for detailed debugging
        traceback.print_exc()
        print(f"Error calculating score: {type(e).__name__}: {e}")
        return jsonify({"error": "Failed to calculate score", "details": str(e)}), 500


# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

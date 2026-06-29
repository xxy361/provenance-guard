import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = "llama-3.3-70b-versatile"

# --- Combined Score Weights ---
LLM_WEIGHT = 0.6
STYLO_WEIGHT = 0.4

# --- Confidence Thresholds ---
AI_THRESHOLD = 0.7
HUMAN_THRESHOLD = 0.4

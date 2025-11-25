import google.generativeai as genai

# New API key
GEMINI_API_KEY = "AIzaSyD1fL-wyHCrDOO1uSLvYRitKhwXPSnd23M"

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

print("🧪 Testing Gemini 2.5 Flash API...")
print(f"📌 Model: gemini-2.5-flash")

try:
    response = model.generate_content("Say hello in 3 words")
    print(f"✅ SUCCESS! API is working!")
    print(f"📝 Response: {response.text}")
except Exception as e:
    print(f"❌ ERROR: {e}")


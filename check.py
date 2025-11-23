
import google.generativeai as genai
import os

# Replace YOUR_API_KEY with your actual key
os.environ["GOOGLE_API_KEY"] = "YOUR_API_KEY"
genai.configure(api_key="AIzaSyBtgt_Lc8OWNIcNuIZc6XyONzd-6z8h8y8")

for m in genai.list_models():
    print(m.name)
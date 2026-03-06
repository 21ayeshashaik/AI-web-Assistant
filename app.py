# from flask import Flask, request, jsonify
# from flask_cors import CORS
# from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# app = Flask(__name__)
# CORS(app) 

# print("Downloading/Loading model... This might take a minute.")
# repo_id = "prem415/my-chrome-summarizer"  
# tokenizer = AutoTokenizer.from_pretrained(repo_id)
# model = AutoModelForSeq2SeqLM.from_pretrained(repo_id)
# print("Model loaded successfully! Waiting for Chrome Extension...")

# @app.route('/process', methods=['POST'])
# def process_text():
#     data = request.json
#     text = data.get("text", "")
#     task = data.get("task", "summarize") # Gets which button was clicked

#     if not text:
#         return jsonify({"error": "No text found on this webpage"}), 400

#     try:
#         # Webpages are huge. We limit the text to ~2500 characters so the model doesn't crash
#         safe_text = text[:2500] 

#         # Change the prompt based on the button clicked
#         if task == "summarize":
#             input_text = "summarize: " + safe_text
#             max_len = 150
#         elif task == "flashcards":
#             input_text = "generate flashcards: " + safe_text
#             max_len = 200
#         elif task == "mcq":
#             input_text = "generate mcq: " + safe_text
#             max_len = 200
#         else:
#             input_text = "summarize: " + safe_text
#             max_len = 150
        
#         # Convert text to tokens
#         input_ids = tokenizer(input_text, return_tensors="pt", max_length=512, truncation=True).input_ids
        
#         # Generate the output
#         outputs = model.generate(input_ids, max_length=max_len, min_length=20, num_beams=4, early_stopping=True)
#         result = tokenizer.decode(outputs[0], skip_special_tokens=True)

#         return jsonify({"result": result})
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)

#UPGRADED VERSION 
import torch
from flask import Flask, request, jsonify
from flask_cors import CORS
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

app = Flask(__name__)
CORS(app) 

print("Downloading/Loading model... This might take a minute.")
repo_id = "prem415/my-chrome-summarizer"  
tokenizer = AutoTokenizer.from_pretrained(repo_id)
model = AutoModelForSeq2SeqLM.from_pretrained(repo_id)

# AUTO-SPEED: Automatically use your computer's GPU if available to completely remove lag
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

print(f"Model loaded successfully on {device.upper()}! Waiting for Chrome Extension...")

@app.route('/process', methods=['POST'])
def process_text():
    data = request.json
    text = data.get("text", "")
    task = data.get("task", "summarize")

    if not text:
        return jsonify({"error": "No text found on this webpage"}), 400

    try:
        # 1. READ MORE: Increased from 2500 to 6000 characters so it reads much more of the page
        safe_text = text[:6000] 

        # 2. GENERATE MORE: Increased lengths for bigger, more detailed outputs
        if task == "summarize":
            input_text = "summarize: " + safe_text
            max_len = 450  # Gives a much longer summary
            min_len = 60   # Forces it to not give a 1-sentence answer
        elif task == "flashcards":
            input_text = "generate flashcards: " + safe_text
            max_len = 350
            min_len = 30
        elif task == "mcq":
            input_text = "generate mcq: " + safe_text
            max_len = 350
            min_len = 30
        else:
            input_text = "summarize: " + safe_text
            max_len = 250
            min_len = 30
        
        # 3. TOKENIZE MORE: Increased max_length from 512 to 1024 words/tokens
        input_ids = tokenizer(
            input_text, 
            return_tensors="pt", 
            max_length=1024, 
            truncation=True
        ).input_ids.to(device) # Send data to the fast hardware
        
        # 4. PREVENT LAG: 'torch.no_grad()' stops the app from eating up all your RAM
        with torch.no_grad():
            outputs = model.generate(
                input_ids, 
                max_length=max_len, 
                min_length=min_len, 
                num_beams=2, # LOWERED from 4 to 2: Generates 2x faster with almost no quality loss
                early_stopping=True,
                use_cache=True # Speeds up repetitive token generation
            )
            
        result = tokenizer.decode(outputs[0], skip_special_tokens=True)

        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
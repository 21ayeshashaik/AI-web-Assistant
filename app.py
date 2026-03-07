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
import gc # Garbage collector to free RAM
import re
import ast
from flask import Flask, request, jsonify
from flask_cors import CORS
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

app = Flask(__name__)
CORS(app) 

# AUTO-SPEED: Automatically use your computer's GPU if available to completely remove lag
device = "cuda" if torch.cuda.is_available() else "cpu"

# Global variables to hold the "currently active" model
current_model = None
current_tokenizer = None
current_task_type = None # Track if we have 'main' or 'mcq' loaded

# --- CONFIGURATION: Set your paths here ---
PATH_MAIN = "prem415/my-chrome-summarizer"  
# Pull safely from Hugging Face Cloud
PATH_MCQ = "Minnu21/my-chrome-mcqmodel" 

def load_model(task_type):
    global current_model, current_tokenizer, current_task_type
    
    # If the right model is already loaded, do nothing
    if current_task_type == task_type:
        return

    print(f"--- Swapping model to: {task_type.upper()} ---")
    
    # 1. Clear existing model from RAM
    if current_model is not None:
        del current_model
        del current_tokenizer
        # Force Python and Windows to actually release the memory
        gc.collect() 
        if device == "cuda":
            torch.cuda.empty_cache()

    # 2. Load the new model
    path = PATH_MCQ if task_type == "mcq" else PATH_MAIN
    
    print(f"Loading '{path}'...")
    current_tokenizer = AutoTokenizer.from_pretrained(path)
    current_model = AutoModelForSeq2SeqLM.from_pretrained(path).to(device)
    current_task_type = task_type
    print(f"--- {task_type.upper()} model loaded successfully on {device.upper()}! ---")

# =========================
# MCQ Helper Functions
# =========================
def clean_and_validate_mcq(mcq_text):
    try:
        question = ""
        options = []
        answer = ""

        if "question:" in mcq_text.lower():
            question = mcq_text.split("question:", 1)[1].split("options:")[0].strip()
            
        # VERY AGGRESSIVE FILTERING
        # Ignore if the question isn't actually a question or is too short
        if not question.endswith("?"):
            return None
        if len(question) < 15:
            return None
            
        # Filter out AI hallucinations about "MCQ formats"
        bad_phrases = ["multiple choice question", "how many options", "what is the answer", "what is multiple choice"]
        for bad in bad_phrases:
            if bad in question.lower():
                return None

        if "options:" in mcq_text.lower():
            opt_part = mcq_text.split("options:", 1)[1].split("answer:")[0].strip()
            try:
                options = ast.literal_eval(opt_part)
            except:
                options = re.findall(r"'(.*?)'", opt_part)

        if "answer:" in mcq_text.lower():
            answer = mcq_text.split("answer:", 1)[1].strip()

        clean_options = []
        for opt in options:
            opt = opt.strip()
            if opt.lower() in ["response:", "and", "successful", ""]:
                continue
            if len(opt) < 2:
                continue
            clean_options.append(opt)

        clean_options = list(dict.fromkeys(clean_options))
        
        # If the model didn't even generate at least 2 real options, reject it
        if len(clean_options) < 2:
            return None

        # Auto add filler options if less than 4
        filler = [
            "All of the above",
            "None of the above",
            "Both A and B",
            "Only A"
        ]

        # Use index carefully
        filler_idx = 0
        while len(clean_options) < 4 and filler_idx < len(filler):
            if filler[filler_idx] not in clean_options:
                clean_options.append(filler[filler_idx])
            filler_idx += 1

        clean_options = clean_options[:4]

        # Ensure answer exists
        if not answer:
            return None
            
        if answer not in clean_options:
            clean_options[0] = answer

        return {
            "question": question,
            "options": clean_options,
            "answer": answer
        }

    except:
        return None

@app.route('/process', methods=['POST'])
def process_text():
    data = request.json
    text = data.get("text", "")
    task = data.get("task", "summarize")

    if not text:
        return jsonify({"error": "No text found on this webpage"}), 400

    try:
        # Guarantee we don't read the whole internet
        safe_text = text[:12000] # Increased from 6,000 to 12,000 characters (approx 2,000 words)

        if task in ["mcq", "flashcards"]:
            load_model("mcq")
            
            # Split the raw website text into sentences
            sentences = re.split(r'[.!?]', safe_text)
            sentences = [s.strip() for s in sentences if len(s.split()) > 8]
            
            # Limit sentences to prevent server from hanging on huge websites
            sentences = sentences[:25] 
            
            valid_mcqs = []
            
            # FAST GENERATION LOOP: Stop exactly when we hit 10 good items!
            for sentence in sentences:
                input_text = "Generate a multiple choice question with 4 meaningful options and one correct answer: " + sentence
                
                inputs = current_tokenizer.encode(
                    input_text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512
                ).to(device)

                with torch.no_grad():
                    outputs = current_model.generate(
                        inputs,
                        max_length=256,
                        num_beams=4,
                        temperature=0.8,
                        top_p=0.9,
                        repetition_penalty=2.0,
                        early_stopping=True
                    )
                
                result = current_tokenizer.decode(outputs[0], skip_special_tokens=True)
                
                cleaned = clean_and_validate_mcq(result)
                if cleaned:
                    if not any(mq['question'] == cleaned['question'] for mq in valid_mcqs):
                        valid_mcqs.append(cleaned)
                
                if len(valid_mcqs) >= 10:
                    break
                    
            if not valid_mcqs:
                return jsonify({"result": "Error: Could not generate valid items from the text provided."})

            return jsonify({"items": valid_mcqs, "task": task})
                
        else:
            # Main model tasks (summarize)
            load_model("main") 
            input_text = "summarize: " + safe_text
            max_len = 450
            min_len = 60
            
            input_ids = current_tokenizer(
                input_text, 
                return_tensors="pt", 
                max_length=1500,
                truncation=True
            ).input_ids.to(device)
            
            with torch.no_grad():
                outputs = current_model.generate(
                    input_ids, 
                    max_length=max_len, 
                    min_length=min_len, 
                    num_beams=2,
                    early_stopping=True,
                    use_cache=True 
                )
                
            result = current_tokenizer.decode(outputs[0], skip_special_tokens=True)
            return jsonify({"result": result, "task": task})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Load the main model initially at startup so it's ready right away
    print("Initializing Server...")
    load_model("main")
    print("Waiting for Chrome Extension...")
    app.run(debug=True, port=5000)
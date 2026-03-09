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


def clean_and_validate_mcq(mcq_text, distractors_pool=[]):
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
        bad_phrases = [
            "multiple choice", "how many option", "what is the answer", 
            "meaningful option", "meaningful options", "correct answer",
            "four meaningful", "4 meaningful", "how many correct",
            "generate a"
        ]
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

        # Ensure answer exists
        answer = answer.strip('.,;:"!?()[]{}\\/ \t\n\r')
        if not answer:
            return None

        # Smart Helper for Deduplication
        import difflib
        def get_base(s):
            s = str(s).lower().strip('.,;:"!?()[]{}\\/ \t\n\r')
            for prefix in ["the ", "a ", "an "]:
                if s.startswith(prefix):
                    return s[len(prefix):]
            return s
            
        def are_similar(s1, s2):
            b1 = get_base(s1)
            b2 = get_base(s2)
            if b1 == b2: return True
            if len(b1) > 3 and len(b2) > 3:
                # Catch "DBMS" vs "Database Management System (DBMS)"
                if b1 in b2 or b2 in b1: return True
                # Catch slight typos
                if difflib.SequenceMatcher(None, b1, b2).ratio() > 0.85: return True
            return False

        clean_options = []
        for opt in options:
            opt = opt.strip('.,;:"!?()[]{}\\/ \t\n\r')
            
            # More aggressive drop list for standalone prepositions and random AI artifacts
            bad_words = [
                "response", "response:", "and", "successful", "", "the", "a", "an", "data",
                "to", "for", "as", "is", "of", "in", "it", "on", "by", "at", "or", "but", "if", "be", "so"
            ]
            
            if opt.lower() in bad_words:
                continue
            if len(opt) < 2:
                continue
            clean_options.append(opt)

        final_clean_options = []
        
       
        final_clean_options.append(answer)
        
        for opt in clean_options:
            is_dup = False
            for f_opt in final_clean_options:
                if are_similar(opt, f_opt):
                    is_dup = True
                    break
            if not is_dup:
                final_clean_options.append(opt)
                
        # Smart NLP Distractors
        if len(final_clean_options) < 4 and distractors_pool:
            import random
            random.shuffle(distractors_pool)
            for d in distractors_pool:
                is_dup = False
                for f_opt in final_clean_options:
                    if are_similar(d, f_opt):
                        is_dup = True
                        break
                if not is_dup:
                    final_clean_options.append(d)
                if len(final_clean_options) == 4:
                    break

        # Fallback filler
        filler = ["All of the above", "None of the above", "Both A and B", "Only A"]
        filler_idx = 0
        while len(final_clean_options) < 4 and filler_idx < len(filler):
            is_dup = False
            for f_opt in final_clean_options:
                if are_similar(filler[filler_idx], f_opt):
                    is_dup = True
                    break
            if not is_dup:
                final_clean_options.append(filler[filler_idx])
            filler_idx += 1

        final_clean_options = final_clean_options[:4]
        
        import random
        random.shuffle(final_clean_options)

        return {
            "question": question,
            "options": final_clean_options,
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
            
            # --- NLP Distractor Setup (Smart Logic) ---
            distractors_pool = []
            try:
                # Fallback to pure regex extraction for Python 3.14 compatibility
                # 1. Grab Capitalized Phrases (Entities, Topics, Proper Nouns)
                capitalized_phrases = re.findall(r'\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b', safe_text)
                
                # 2. Grab important common words
                words = re.findall(r'\b[a-zA-Z]{5,15}\b', safe_text.lower())
                from collections import Counter
                common_words = [w for w, c in Counter(words).most_common(50)]
                
                # Combine and filter
                raw_pool = capitalized_phrases + [w.capitalize() for w in common_words]
                
                # Strict Stopwords
                stops = ["these", "those", "their", "there", "which", "would", "could", "should", "other", "about", "after", "where", "while", "under"]
                
                for term in raw_pool:
                    c_text = term.strip()
                    if 3 < len(c_text) < 30 and "\n" not in c_text:
                        if c_text.lower() in stops: continue
                        if c_text.lower().startswith("the "): c_text = c_text[4:]
                        elif c_text.lower().startswith("a "): c_text = c_text[2:]
                        elif c_text.lower().startswith("an "): c_text = c_text[3:]
                        
                        c_text = c_text.capitalize()
                        if c_text not in distractors_pool and c_text.lower() != "all of the above":
                            distractors_pool.append(c_text)
                            
                import random
                random.shuffle(distractors_pool)
            except Exception as e:
                print("Regex Distractor extraction failed:", e)
            # ----------------------------------------
            
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
                        do_sample=True,
                        temperature=0.8,
                        top_p=0.9,
                        repetition_penalty=2.0,
                        early_stopping=True
                    )
                
                result = current_tokenizer.decode(outputs[0], skip_special_tokens=True)
                
                cleaned = clean_and_validate_mcq(result, distractors_pool)
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
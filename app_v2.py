# In-memory manual checking list
manual_checking_pdfs = []
# Add missing import for os
import os

# does not gemini api , do not segregate answers properly
from flask import Flask, request, jsonify, render_template
import gspread
from google.oauth2.service_account import Credentials
import os

GOOGLE_SHEET_ID = "1_YivMP4BLP-EfkuuSG81ne26tSuB-qCvR4byRjvsCxM"  # Set this in your environment or hardcode for now
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")


# Google Sheets helper
def save_results_to_sheet(sheet_name, rows):
    if not GOOGLE_SHEET_ID:
        print("No GOOGLE_SHEET_ID set, skipping Google Sheets write.")
        return
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=scopes
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        try:
            worksheet = sh.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=sheet_name, rows="100", cols="20")
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    except Exception as e:
        print(f"Error writing to Google Sheet: {e}")


from PIL import Image
import requests
import re
import tempfile
from pdf2image import convert_from_path
from collections import defaultdict
import google.generativeai as genai
import textwrap

app = Flask(__name__)

# make sure to set these environment variables in your .env file or system


# Add this configuration after your Flask app initialization
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY")
OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY")

meta_data = {"questions": [], "general_prompt": ""}  # List of question dictionaries


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/config")
def config_page():
    return render_template("pages/config.html")

@app.route("/upload")
def upload_page():
    return render_template("pages/upload.html")
    
@app.route("/results")
def results_page():
    return render_template("pages/results.html")


@app.route("/api/set-meta", methods=["POST"])
def set_meta():
    data = request.json
    meta_data["questions"] = data.get("questions", [])
    meta_data["general_prompt"] = data.get("general_prompt", "")
    print(f"Meta data set: {meta_data}")
    print(
        "key values:",
        os.environ.get("TOGETHER_API_KEY"),
        os.environ.get("OCR_SPACE_API_KEY"),
    )
    return jsonify({"success": True, "message": "Metadata set successfully."})


@app.route("/api/get-meta", methods=["GET"])
def get_meta():
    return jsonify(meta_data)

@app.route("/api/grade", methods=["POST"])
def grade():
    data = request.json
    question_id = data.get("question_id", "")
    student_answer = data.get("answer_text", "").strip()

    if not meta_data.get("questions"):
        return jsonify({"result": "❌ Please configure questions before grading."})

    if not student_answer:
        return jsonify({"result": "❌ Student answer is missing."})

    # For single question grading
    if len(meta_data["questions"]) == 1:
        question = meta_data["questions"][0]
        result = evaluate_single_answer(question, student_answer)
        max_marks = question.get("max_marks", 0)
        marks_obtained = extract_marks_from_result(result, max_marks)

        return jsonify(
            {
                "result": result,
                "marks_obtained": marks_obtained,
                "max_marks": max_marks,
                "grade_summary": f"{marks_obtained}/{max_marks}",
            }
        )
    else:
        return jsonify({"result": "❌ Use /grade-pdf for multiple questions"})


@app.route("/api/extract-text", methods=["POST"])
def extract_text():
    if "image_file" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image_file = request.files["image_file"]
    image_path = "uploaded_image.png"

    try:
        # Load and compress image
        uploaded_image = Image.open(image_file)
        compressed_image = compress_image_for_ocr(uploaded_image)
        compressed_image.save(image_path, "PNG", optimize=True, quality=85)

        extracted_text = ocr_space_api(image_path, OCR_SPACE_API_KEY)

        if not extracted_text:
            return jsonify({"result": "❌ OCR returned no text to grade."})

        # For single question grading
        if len(meta_data.get("questions", [])) == 1:
            question = meta_data["questions"][0]
            return evaluate_single_answer(question, extracted_text)
        else:
            return jsonify({"result": "❌ Use /grade-pdf for multiple questions"})

    except Exception as e:
        return jsonify({"error": f"Image processing failed: {str(e)}"}), 500

    finally:
        # Clean up uploaded image
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except:
            pass


# def pdf_to_images(pdf_path):
#     """Convert PDF to list of PIL images"""
#     try:
#         # Try with poppler path first
#         return convert_from_path(pdf_path)
#     except Exception as e:
#         print(f"PDF conversion failed: {str(e)}")
#         # Try alternative method or fallback
#         try:
#             import fitz  # PyMuPDF
#             doc = fitz.open(pdf_path)
#             images = []
#             for page_num in range(len(doc)):
#                 page = doc.load_page(page_num)
#                 pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
#                 img_data = pix.tobytes("png")
#                 from io import BytesIO
#                 images.append(Image.open(BytesIO(img_data)))
#             doc.close()
#             return images
#         except ImportError:
#             print("PyMuPDF not available. Please install poppler or PyMuPDF.")
#             return []
#         except Exception as e2:
#             print(f"Alternative PDF processing also failed: {str(e2)}")
#             return []


def extract_text_from_pdf(pdf_path, api_key):
    """Extract text from PDF using OCR with on‑the‑fly compression."""
    try:
        images = pdf_to_images(pdf_path)
        if not images:
            return ""

        full_text = []

        for i, image in enumerate(images, start=1):
            # 1) Compress using your existing function
            compressed_img = compress_image_for_ocr(image)

            # 2) Save as JPEG for smaller file size
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                image_path = tmp.name
                compressed_img.save(image_path, "JPEG")

            size_kb = os.path.getsize(image_path) / 1024
            print(f"Processing page {i} — {size_kb:.1f} KB")

            # 3) Call OCR.space and collect text
            try:
                page_text = ocr_space_api(image_path, api_key)
                if page_text:
                    full_text.append(f"[PAGE {i}]\n{page_text}")
                    print(
                        f"Extracted text from page {i}: {page_text}..."
                    )  # Print first 100 chars
            finally:
                # Always clean up the temp file
                try:
                    os.remove(image_path)
                except OSError:
                    pass

        return "\n\n".join(full_text).strip()

    except Exception as e:
        print(f"PDF processing error: {e}")
        return ""


def segment_answers_with_gemini(images, question_ids):
    """Process each page image with Gemini 1.5 Flash to extract answers"""
    model = genai.GenerativeModel("gemini-1.5-flash-latest")
    answers = defaultdict(str)

    # Create question reference string
    qref = "\n".join([f"{qid}. [Question {qid}]" for qid in question_ids])

    for i, image in enumerate(images):
        try:
            # Prepare optimized prompt
            prompt = textwrap.dedent(
                f"""
            You are processing page {i+1} of an exam answer sheet. 
            The exam contains these questions: {qref}
            
            INSTRUCTIONS:
            1. Identify visible question numbers (e.g., '1', 'Q2', 'Question 3')
            2. Extract all text content exactly as written
            3. Segment text by question
            4. Start each answer with the question ID in brackets like: [Q1] 
            5. Include ALL text exactly as seen
            
            OUTPUT FORMAT:
            - For each question: [QID] Answer text...
            - Don't add any additional text or explanations
            """
            )

            # Process image with Gemini 1.5 Flash
            response = model.generate_content(
                [prompt, image],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1, max_output_tokens=4096
                ),
            )
            page_text = response.text.strip()

            print(f"Gemini 1.5 Flash Page {i+1} response:\n{page_text}\n{'-'*40}")

            # Process Gemini response by finding [QID] markers
            current_qid = None
            for line in page_text.split("\n"):
                line = line.strip()
                # Check for question ID marker at start of line
                q_match = re.match(r"^\[Q?(\d+)\]", line)
                print("q_match", q_match)
                if q_match:
                    current_qid = q_match.group(1)
                    print(f"Found question ID: {current_qid}")
                    # Remove the marker from the answer text
                    line = line.replace(f"[{current_qid}]", "").strip()

                print(current_qid, "type of current qid", type(current_qid))
                print(question_ids, "type of question ids", type(question_ids))
                # Add text to current question if we have a valid ID
                if current_qid:
                    current_qid = "Q" + current_qid
                if current_qid and (current_qid in question_ids):
                    # print(line)
                    answers[current_qid] += line + "\n"

        except Exception as e:
            print(f"Gemini processing error on page {i+1}: {str(e)}")
    # print(answers)
    # Post-process answers to clean up
    for qid in answers:
        # Remove any remaining markers
        answers[qid] = (
            answers[qid].replace("[CONTINUE]", "").replace("[END]", "").strip()
        )
        # Remove duplicate newlines
        answers[qid] = re.sub(r"\n+", "\n", answers[qid])

    # Add missing questions
    for qid in question_ids:
        if qid not in answers or not answers[qid].strip():
            answers[qid] = "❌ Answer not found for this question"

    print("Extracted answers:", answers)
    return answers


# Update the grade_pdf route to use Gemini 1.5 Flash
@app.route("/api/grade-pdf", methods=["POST"])
def grade_pdf():
    if "pdf_file" not in request.files:
        return jsonify({"error": "No PDF uploaded"}), 400

    pdf_file = request.files["pdf_file"]
    temp_path = None

    try:
        # Create temp file and save PDF
        _, temp_path = tempfile.mkstemp(suffix=".pdf")
        pdf_file.save(temp_path)

        # Convert PDF to high-quality images
        images = pdf_to_images(temp_path)
        if not images:
            return (
                jsonify({"error": "PDF conversion failed. No images generated."}),
                400,
            )

        # Get question identifiers
        question_ids = [q["id"] for q in meta_data.get("questions", [])]
        if not question_ids:
            return jsonify({"error": "No questions configured"}), 400

        # Process with Gemini 1.5 Flash
        answers = segment_answers_with_gemini(images, question_ids)
        print(f"Extracted answers: {answers}")  # Debugging output
        print("grading answers...")

        # Grade each answer
        results = []
        total_marks_obtained = 0
        total_max_marks = 0

        for question in meta_data["questions"]:
            qid = question["id"]
            answer_text = answers.get(qid, "")
            max_marks = question.get("max_marks", 0)
            # print(max_marks,"type of max_marks",type(max_marks))
            total_max_marks += int(max_marks)

            # If answer is missing or error marker present
            if not answer_text.strip() or "❌" in answer_text:
                results.append(
                    {
                        "question_id": qid,
                        "result": answer_text or "❌ Answer not found",
                        "answer": "",
                        "marks_obtained": 0,
                        "max_marks": max_marks,
                    }
                )
            else:
                # Grade the actual answer text
                result = evaluate_single_answer(question, answer_text)
                print(f"Grading result for {qid}: {result}")  # Debugging output
                # Extract marks from result if possible (assuming result contains marks like "8/10" or "Marks: 8")
                marks_obtained = extract_marks_from_result(result, max_marks)
                print(f"Marks extracted for {qid}: {marks_obtained} out of {max_marks}")
                print(type(marks_obtained), "type of marks_obtained")
                # Ensure marks_obtained is a number
                try:
                    marks_obtained = float(marks_obtained) if marks_obtained else 0
                except (ValueError, TypeError):
                    marks_obtained = 0
                total_marks_obtained += marks_obtained

                results.append(
                    {
                        "question_id": qid,
                        "result": result,
                        "answer": (
                            answer_text[:500] + "..."
                            if len(answer_text) > 500
                            else answer_text
                        ),
                        "marks_obtained": marks_obtained,
                        "max_marks": max_marks,
                    }
                )

        # Calculate percentage
        percentage = (
            (total_marks_obtained / total_max_marks * 100) if total_max_marks > 0 else 0
        )
        print(
            f"Total marks obtained: {total_marks_obtained} out of {total_max_marks} ({percentage:.1f}%)"
        )

        # Save to Google Sheet
        sheet_rows = [
            [
                "PDF Upload",
                question["id"],
                question["question"],
                r["answer"],
                r["marks_obtained"],
                r["max_marks"],
                r["result"],
                round(percentage, 2),
            ]
            for question, r in zip(meta_data["questions"], results)
        ]
        save_results_to_sheet("PDF Results", sheet_rows)

        return jsonify(
            {
                "results": results,
                "overall_score": {
                    "total_marks_obtained": total_marks_obtained,
                    "total_max_marks": total_max_marks,
                    "percentage": round(percentage, 2),
                    "grade_summary": f"{total_marks_obtained}/{total_max_marks} ({percentage:.1f}%)",
                },
            }
        )

    except Exception as e:
        error_msg = f"Processing failed: {str(e)}"
        print(error_msg)
        return jsonify({"error": error_msg}), 500

    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass


# Update pdf_to_images for better quality
def pdf_to_images(pdf_path, dpi=300):
    """Convert PDF to list of PIL images with specified DPI"""
    try:
        return convert_from_path(pdf_path, dpi=dpi)
    except:
        try:
            import fitz

            doc = fitz.open(pdf_path)
            images = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
                img_data = pix.tobytes("png")
                from io import BytesIO

                images.append(Image.open(BytesIO(img_data)))
            doc.close()
            return images
        except Exception as e:
            print(f"PDF conversion error: {str(e)}")
            return []


# Update pdf_to_images to ensure quality


def ocr_space_api(image_path, api_key):
    url = "https://api.ocr.space/parse/image"
    try:
        with open(image_path, "rb") as f:
            response = requests.post(
                url,
                files={"filename": f},
                data={
                    "apikey": api_key,
                    "language": "eng",
                    "isOverlayRequired": True,  # Needed for confidence
                    "ocrengine": 2,
                },
                timeout=30,
            )
        result = response.json()

        if result.get("IsErroredOnProcessing"):
            error_msg = result.get("ErrorMessage", "Unknown OCR error")
            print(f"❌ OCR.Space Error: {error_msg}")
            return "", 0

        parsed_results = result.get("ParsedResults", [])
        if not parsed_results or "ParsedText" not in parsed_results[0]:
            print("❌ OCR returned no text")
            return "", 0

        text = parsed_results[0]["ParsedText"].strip()
        # Calculate average confidence if available
        avg_conf = 100
        if (
            "TextOverlay" in parsed_results[0]
            and "Lines" in parsed_results[0]["TextOverlay"]
        ):
            lines = parsed_results[0]["TextOverlay"]["Lines"]
            confs = [
                float(line.get("Words", [{}])[0].get("WordConfidence", 100))
                for line in lines
                if line.get("Words")
            ]
            if confs:
                avg_conf = sum(confs) / len(confs)
        return text, avg_conf
    except Exception as e:
        print(f"OCR processing failed: {str(e)}")
        return "", 0


def evaluate_single_answer(question_meta, student_answer):
    """Grade a single answer using question-specific metadata"""
    print(question_meta.values())
    # check if all required metadata is present except for evaluation prompt
    required_keys = ["id", "question", "rubric", "max_marks"]
    for key in required_keys:
        if key not in question_meta:
            return f"❌ Missing required metadata: {key} for question {question_meta.get('id', 'unknown')}"

    # Use question-specific prompt or general prompt
    prompt = question_meta.get("prompt", meta_data.get("general_prompt", ""))

    # Auto-append instruction to ignore OCR spelling mistakes and request marks
    if "ignore" not in prompt.lower():
        prompt += "\n\nNote: Ignore spelling or OCR-related mistakes. Focus on meaning and rubric."

    # Add instruction to include numerical marks
    prompt += f"\n\nIMPORTANT: End your response with 'Marks: X/{question_meta['max_marks']}' where X is the marks awarded."

    # Build the evaluation prompt
    full_prompt = f"""
{prompt}

---

Question:
{question_meta['question']}

Rubric:
{question_meta['rubric']}

Maximum Marks: {question_meta['max_marks']}

Student Answer:
{student_answer.strip()}
""".strip()

    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "messages": [
            {
                "role": "system",
                "content": "You are a strict and fair examiner. Grade based only on rubric. Be brief and fair. Always end with 'Marks: X/total' format.",
            },
            {"role": "user", "content": full_prompt},
        ],
        "max_tokens": 512,
        "temperature": 0.1,
        "top_p": 0.9,
    }

    try:
        response = requests.post(
            "https://api.together.xyz/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        json_response = response.json()

        if "choices" in json_response and json_response["choices"]:
            result = json_response["choices"][0]["message"]["content"].strip()
            return result
        elif "error" in json_response:
            return f"❌ API Error: {json_response['error'].get('message', 'Unknown error')}"
        else:
            return "❌ Unexpected response format from Together.ai."

    except requests.exceptions.RequestException as req_err:
        return f"❌ Network error: {str(req_err)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


def compress_image_for_ocr(image, max_size_kb=900):
    """
    Compress image to stay under OCR API size limits
    Returns compressed PIL Image
    """
    import io

    # Start with original image
    compressed = image.copy()

    # Try different compression levels
    for quality in [85, 75, 65, 55, 45]:
        # Save to bytes to check size
        img_byte_arr = io.BytesIO()
        compressed.save(img_byte_arr, format="PNG", optimize=True, quality=quality)
        size_kb = len(img_byte_arr.getvalue()) / 1024

        if size_kb <= max_size_kb:
            img_byte_arr.seek(0)
            return Image.open(img_byte_arr)

        # If still too large, resize image
        if quality == 45:
            width, height = compressed.size
            new_width = int(width * 0.8)
            new_height = int(height * 0.8)
            compressed = compressed.resize(
                (new_width, new_height), Image.Resampling.LANCZOS
            )

    return compressed


def extract_marks_from_result(result_text, max_marks):
    """Extract numerical marks from grading result text"""
    import re

    # Common patterns for marks in evaluation results
    patterns = [
        r"(\d+(?:\.\d+)?)\s*/\s*\d+",  # "8/10" or "7.5/10"
        r"marks?\s*:?\s*(\d+(?:\.\d+)?)",  # "Marks: 8" or "marks 8"
        r"score\s*:?\s*(\d+(?:\.\d+)?)",  # "Score: 8"
        r"(\d+(?:\.\d+)?)\s*out\s*of",  # "8 out of"
        r"(\d+(?:\.\d+)?)\s*points?",  # "8 points"
    ]

    for pattern in patterns:
        match = re.search(pattern, result_text.lower())
        if match:
            try:
                marks = float(match.group(1))
                # Ensure marks don't exceed max_marks
                return min(marks, float(max_marks))
            except ValueError:
                continue

    # If no marks found, try to infer from text
    result_lower = result_text.lower()
    if any(word in result_lower for word in ["excellent", "perfect", "full marks"]):
        return max_marks
    elif any(word in result_lower for word in ["good", "mostly correct"]):
        return max_marks * 0.8
    elif any(word in result_lower for word in ["partial", "some credit"]):
        return max_marks * 0.5
    elif any(word in result_lower for word in ["poor", "incorrect", "wrong"]):
        return 0

    # Default to 0 if cannot determine
    return 0


# New route: Upload a zip of PDFs, extract, process all, and return results by PDF name
from zipfile import ZipFile


@app.route("/api/grade-pdf-folder", methods=["POST"])
def grade_pdf_folder():
    if "pdf_folder" not in request.files:
        return jsonify({"error": "No folder (zip) uploaded"}), 400

    zip_file = request.files["pdf_folder"]
    temp_zip_path = None
    extract_dir = os.path.join(os.getcwd(), "uploads", "pdf_batch")
    os.makedirs(extract_dir, exist_ok=True)

    all_results = {}
    global manual_checking_pdfs
    manual_checking_pdfs = []
    manual_checking_confidences = (
        []
    )  # List of dicts: {"filename": ..., "avg_confidence": ...}
    try:
        # Save zip temporarily
        _, temp_zip_path = tempfile.mkstemp(suffix=".zip")
        zip_file.save(temp_zip_path)

        # Extract all PDFs
        from zipfile import ZipFile

        with ZipFile(temp_zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        # Find all PDFs in extracted folder (recursively)
        pdf_files = []
        for root, _, files in os.walk(extract_dir):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, f))

        # Get question IDs
        question_ids = [q["id"] for q in meta_data.get("questions", [])]

        for pdf_path in pdf_files:
            try:
                images = pdf_to_images(pdf_path)
                if not images:
                    all_results[os.path.basename(pdf_path)] = {
                        "error": "PDF conversion failed"
                    }
                    continue
                # OCR confidence check (average over all pages)
                confidences = []
                for i, image in enumerate(images):
                    with tempfile.NamedTemporaryFile(
                        suffix=".jpg", delete=False
                    ) as tmp:
                        image_path = tmp.name
                        image.save(image_path, "JPEG")
                    _, avg_conf = ocr_space_api(image_path, OCR_SPACE_API_KEY)
                    confidences.append(avg_conf)
                    try:
                        os.remove(image_path)
                    except:
                        pass
                pdf_avg_conf = (
                    sum(confidences) / len(confidences) if confidences else 100
                )
                if pdf_avg_conf < 85:
                    manual_checking_pdfs.append(os.path.basename(pdf_path))
                    manual_checking_confidences.append(
                        {
                            "filename": os.path.basename(pdf_path),
                            "avg_confidence": pdf_avg_conf,
                        }
                    )
                    all_results[os.path.basename(pdf_path)] = {
                        "manual_check_required": True,
                        "avg_confidence": pdf_avg_conf,
                        "message": "Low OCR confidence, needs manual checking.",
                    }
                    continue
                # If confidence is good, proceed as usual
                answers = segment_answers_with_gemini(images, question_ids)
                results = []
                total_marks_obtained = 0
                total_max_marks = 0
                for question in meta_data["questions"]:
                    qid = question["id"]
                    answer_text = answers.get(qid, "")
                    max_marks = question.get("max_marks", 0)
                    total_max_marks += int(max_marks)
                    if not answer_text.strip() or "❌" in answer_text:
                        results.append(
                            {
                                "question_id": qid,
                                "result": answer_text or "❌ Answer not found",
                                "answer": "",
                                "marks_obtained": 0,
                                "max_marks": max_marks,
                            }
                        )
                    else:
                        result = evaluate_single_answer(question, answer_text)
                        marks_obtained = extract_marks_from_result(result, max_marks)
                        try:
                            marks_obtained = (
                                float(marks_obtained) if marks_obtained else 0
                            )
                        except (ValueError, TypeError):
                            marks_obtained = 0
                        total_marks_obtained += marks_obtained
                        results.append(
                            {
                                "question_id": qid,
                                "result": result,
                                "answer": (
                                    answer_text[:500] + "..."
                                    if len(answer_text) > 500
                                    else answer_text
                                ),
                                "marks_obtained": marks_obtained,
                                "max_marks": max_marks,
                            }
                        )
                percentage = (
                    (total_marks_obtained / total_max_marks * 100)
                    if total_max_marks > 0
                    else 0
                )
                all_results[os.path.basename(pdf_path)] = {
                    "results": results,
                    "overall_score": {
                        "total_marks_obtained": total_marks_obtained,
                        "total_max_marks": total_max_marks,
                        "percentage": round(percentage, 2),
                        "grade_summary": f"{total_marks_obtained}/{total_max_marks} ({percentage:.1f}%)",
                    },
                    "avg_confidence": pdf_avg_conf,
                }
                # Save to Google Sheet for each PDF
                sheet_rows = [
                    [
                        os.path.basename(pdf_path),
                        question["id"],
                        question["question"],
                        r["answer"],
                        r["marks_obtained"],
                        r["max_marks"],
                        r["result"],
                        round(percentage, 2),
                    ]
                    for question, r in zip(meta_data["questions"], results)
                ]
                save_results_to_sheet("Batch PDF Results", sheet_rows)
            except Exception as e:
                all_results[os.path.basename(pdf_path)] = {
                    "error": f"Processing failed: {str(e)}"
                }

        # Save confidences for manual check API
        global manual_checking_confidences_global
        manual_checking_confidences_global = manual_checking_confidences
        return jsonify({"pdf_results": all_results})
    except Exception as e:
        return jsonify({"error": f"Batch processing failed: {str(e)}"}), 500
    finally:
        # Clean up temp zip and extracted files
        if temp_zip_path and os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except:
                pass
        if os.path.exists(extract_dir):
            import shutil

            try:
                shutil.rmtree(extract_dir)
            except:
                pass


# Route to get manual checking list (with confidence)
@app.route("/api/manual-check-list", methods=["GET"])
def manual_check_list():
    global manual_checking_confidences_global
    # Fallback for backward compatibility
    if "manual_checking_confidences_global" not in globals():
        return jsonify({"manual_checking_pdfs": manual_checking_pdfs})
    return jsonify({"manual_checking_pdfs": manual_checking_confidences_global})


if __name__ == "__main__":
    app.run(debug=True)

# AI Answer Sheet Evaluator

An AI-powered answer sheet grading system built with **Flask**, **Google Gemini**, and **OCR.space**. Teachers can configure exam questions with mark allocations, then upload student answer sheets as images or PDFs — the system automatically extracts the text, segments answers per question, grades each answer using Gemini, and logs results to Google Sheets.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [How It Works](#how-it-works)
- [API Reference](#api-reference)
- [Setup & Running](#setup--running)

---

## Overview

The system solves the time-consuming task of manually grading handwritten/printed answer sheets. You configure your questions once, upload the student's answer sheet, and receive:

- Per-question grading feedback
- Marks obtained vs maximum marks
- An overall grade summary
- Results automatically saved to a Google Sheet

---

## Features

- **Single image grading** — Upload a photo of a student's handwritten answer
- **Multi-question PDF grading** — Upload a full PDF; Gemini 1.5 Flash segments answers per question automatically
- **OCR.space integration** — Extracts text from images using cloud OCR
- **Gemini AI grading** — Evaluates answers against the expected answer and assigns marks
- **Google Sheets logging** — All results appended to a Google Sheet for record-keeping
- **Image compression** — Uploaded images are automatically compressed before OCR

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python, Flask |
| AI Grading | Google Gemini 1.5 Flash (`google-generativeai`) |
| OCR | OCR.space API |
| PDF Processing | `pdf2image` / PyMuPDF (`fitz`) |
| Image Handling | Pillow |
| Spreadsheet | Google Sheets API (`gspread`) |
| Frontend | HTML/CSS (`templates/`) |

---

## Project Structure

```
AI_Answer_Sheet_Evaluator/
├── app_v2.py            # Main Flask application
├── templates/
│   └── index1.html      # Web interface
├── dataset/             # Sample datasets
├── service_account.json # Google Sheets service account credentials
├── .env                 # API keys (never commit this!)
└── todo.txt             # Development notes
```

---

## Environment Variables

Create a `.env` file (or set system environment variables):

```env
GOOGLE_API_KEY=your_gemini_api_key
TOGETHER_API_KEY=your_together_api_key
OCR_SPACE_API_KEY=your_ocr_space_api_key
```

Also set `GOOGLE_SHEET_ID` inside `app_v2.py` to your target spreadsheet ID.

---

## How It Works

### Single Answer (Image)
1. Teacher sets question metadata via `POST /set-meta` (question text, max marks, expected answer).
2. Student image is uploaded to `POST /extract-text`.
3. OCR.space extracts text from the image.
4. Gemini evaluates the extracted answer and assigns a score.

### Multi-Question PDF
1. Teacher sets multiple questions + marks via `POST /set-meta`.
2. PDF is uploaded to `POST /grade-pdf`.
3. `pdf_to_images()` converts each page to a high-DPI image.
4. Gemini 1.5 Flash reads each page, identifies question markers (e.g., `[Q1]`), and segments answers.
5. Each answer is individually graded by Gemini.
6. Results (marks per question, percentage, feedback) are returned as JSON and appended to Google Sheets.

---

## API Reference

### `GET /`
Returns the grading interface.

### `POST /set-meta`
Configure questions before grading.
```json
{
  "questions": [
    {
      "id": "Q1",
      "question": "What is Newton's second law?",
      "expected_answer": "F = ma",
      "max_marks": 5
    }
  ],
  "general_prompt": "Be strict with partial credit"
}
```

### `POST /grade`
Grade a single text answer.
```json
{ "student_answer": "Force equals mass times acceleration." }
```

### `POST /extract-text`
Upload an image (`multipart/form-data`, field `image`) for OCR + grading.

### `POST /grade-pdf`
Upload a PDF (`multipart/form-data`, field `pdf`) for full multi-question grading.

---

## Setup & Running

```bash
git clone https://github.com/jaideepj2004/AI_Answer_Sheet_Evaluator.git
cd AI_Answer_Sheet_Evaluator

pip install flask google-generativeai gspread google-auth pillow pdf2image requests

# Set environment variables in .env
python app_v2.py
```

Open `http://127.0.0.1:5000`.

> **Note:** You need a valid Google Gemini API key, OCR.space API key, and a Google service account JSON file with access to your target Google Sheet.

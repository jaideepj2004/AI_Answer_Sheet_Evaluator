# AI Answer Sheet Evaluator

## Overview
AI Answer Sheet Evaluator is a web application designed to automate the evaluation of answer sheets using AI and Google Sheets integration. It provides a user-friendly interface for uploading answer sheet PDFs, processes them, and records results in a Google Sheet. Manual checking is supported for cases where automation is insufficient.

## Features
- Upload answer sheet PDFs for evaluation
- Automated extraction and grading of answers
- Manual checking list for PDFs requiring human review
- Results saved to Google Sheets
- Modern web interface (see `templates/index1.html`)

## Technologies Used
- Python 3.11+
- Flask (web framework)
- Google Sheets API (via `gspread` and `google-auth`)
- Pillow (image processing)
- HTML/CSS (frontend)

## Setup Instructions
1. **Clone the repository:**
    ```powershell
    git clone https://github.com/jaideepj2004/AI_Answer_Sheet_Evaluator.git
    ```
2. **Install Python dependencies:**
	- Create a virtual environment (optional but recommended)
	- Install required packages:
	  ```powershell
	  pip install flask gspread google-auth pillow
	  ```
3. **Google Sheets Setup:**
	- Obtain a Google service account and download the `service_account.json` file.
	- Place `service_account.json` in the project root.
	- Set your Google Sheet ID in `app_v2.py` (variable: `GOOGLE_SHEET_ID`).

## Running the Application
1. Start the Flask app:
	```powershell
	python app_v2.py
	```
2. Open your browser and navigate to `http://localhost:5000`.

## Usage
- Use the web interface to upload answer sheet PDFs.
- The app will process the sheets and attempt to evaluate answers automatically.
- Results are appended to the specified Google Sheet.
- PDFs requiring manual review are added to a manual checking list.

## File Structure
- `app_v2.py` - Main Flask application and backend logic
- `templates/index1.html` - Web interface
- `service_account.json` - Google API credentials
- `uploads/` - Directory for uploaded PDFs
- `todo.txt` - Project notes and todos

## Notes
- The app does **not** use Gemini API for answer segregation.
- Some answers may not be segregated properly; manual checking is supported.
- Ensure your Google service account has access to the target Google Sheet.

## License
This project is for educational purposes. Please check the repository for license details.
# clinical-report-report
clinical report using cosmic db

# 1. Virtual Environment
python3 -m venv venv

# 2. Activate Virtual Environment
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 3. Dependency installation
pip install -r requirements.txt

# 4. Report Generation Script
python generate_report.py report_data.json --view clinician
python generate_report.py report_data.json --view patient
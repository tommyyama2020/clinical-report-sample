# clinical-report-report
clinical report using cosmic db

# 1. 仮想環境作成
python3 -m venv venv

# 2. 有効化
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 3. 依存関係インストール
pip install -r requirements.txt

# 4. レポート生成
python generate_report.py report_data.json --view clinician
python generate_report.py report_data.json --view patient
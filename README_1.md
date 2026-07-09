# Drug Interaction Checker

A web-based clinical decision support tool built with Python Flask that checks for dangerous interactions between medications. Designed to help healthcare professionals in resource-limited settings quickly verify drug safety — and now expandable through community-submitted interaction data.

## Features

### Interaction Checking
- Search and check interactions between any two drugs
- Severity classification (Major, Moderate, Minor)
- Detailed clinical effects and management guidance
- Autocomplete drug search
- Checks both the verified built-in database and community-submitted interactions

### Drug Database
- 25 common medications across multiple drug classes
- Antibiotics, antimalarials, anticoagulants, antidiabetics, and more
- Generic names, drug classes, and common uses included

### Drug Profile Lookup
- View all known interactions for any specific drug
- Sorted by severity for quick clinical reference
- One-click access from the drug database grid

### Community Interaction Submissions (New)
- Public submission form at `/submit-interaction` allowing healthcare professionals to add interactions not yet in the database
- Collects submitter name, email, and profession (Pharmacist, Physician, Nurse, etc.) for credibility context
- Submissions go live immediately in the interaction checker, clearly labeled as community-sourced versus verified
- No password required for public users — designed to encourage participation from practicing clinicians

### Admin Review Dashboard (New)
- Password-protected admin panel at `/admin` for reviewing all community-submitted interactions
- Summary statistics: total submissions, unique submitters
- Visual breakdown of submissions by severity and by submitter profession
- Full submissions table with submitter details and interaction descriptions
- One-click CSV export of all community submissions for external analysis and reporting

### Clinical Information Provided
- Interaction description
- Clinical effects of combining drugs
- Recommended clinical management steps
- Source label (Verified database vs Community submitted) so users can weigh confidence appropriately

## How to Run

1. Install Python 3 on your computer
2. Install Flask:
   pip install flask
3. Navigate to this folder in your terminal
4. Run the application:
   python app.py
5. Open your browser and go to:
   http://127.0.0.1:5000

### Additional Routes
- Submit a new interaction: http://127.0.0.1:5000/submit-interaction
- Admin login: http://127.0.0.1:5000/admin/login
- Admin dashboard (after login): http://127.0.0.1:5000/admin

**Note:** Before deploying publicly, set `ADMIN_PASSWORD` and `SECRET_KEY` as environment variables rather than hardcoding them in app.py.

## Technologies Used
- Python 3
- Flask (web framework)
- SQLite3 (database)
- HTML5 and CSS3
- JavaScript (vanilla, no frameworks)

## Database Schema
- drugs - stores drug name, generic name, class, description, and uses (built-in verified database)
- interactions - stores verified interaction pairs with severity, effects, and management advice
- submitters - stores name, email, and profession of anyone submitting a community interaction
- submitted_interactions - stores community-submitted interaction pairs, linked to their submitter

## Clinical Disclaimer
This tool is intended to support clinical decision making and demonstrate health informatics concepts. It does not replace professional medical judgment, official drug references, or consultation with a qualified pharmacist or physician. Community-submitted interactions are published immediately without independent verification and should be treated as supplementary information rather than a substitute for the verified database entries.

## Research Context
This project was built as part of research into clinical decision support systems and participatory data collection for low-resource healthcare settings in Sub-Saharan Africa. The community submission feature allows the interaction database to grow through direct contribution from practicing pharmacists and clinicians, complementing the curated reference dataset.

## Author
Emmanuel Owusu Adu
Computer Science Graduate | Health Informatics Researcher
Interests: Health Informatics, Information Systems, Information Science
https://www.linkedin.com/in/emmanuel-owusu-adu-037084341

# Drug Interaction Checker

A web-based clinical decision support tool built with Python Flask that checks for dangerous interactions between medications. Designed to help healthcare professionals in resource-limited settings quickly verify drug safety.

## Features

### Interaction Checking

- Search and check interactions between any two drugs
- Severity classification (Major, Moderate, Minor)
- Detailed clinical effects and management guidance
- Autocomplete drug search

### Drug Database

- 25 common medications across multiple drug classes
- Antibiotics, antimalarials, anticoagulants, antidiabetics, and more
- Generic names, drug classes, and common uses included

### Drug Profile Lookup

- View all known interactions for any specific drug
- Sorted by severity for quick clinical reference
- One-click access from the drug database grid

### Clinical Information Provided

- Interaction description
- Clinical effects of combining drugs
- Recommended clinical management steps

## How to Run

1. Install Python 3 on your computer
1. Install Flask:
   pip install flask
1. Navigate to this folder in your terminal
1. Run the application:
   python app.py
1. Open your browser and go to:
   <http://127.0.0.1:5000>

## Technologies Used

- Python 3
- Flask (web framework)
- SQLite3 (database)
- HTML5 and CSS3
- JavaScript (vanilla, no frameworks)

## Database Schema

- drugs - stores drug name, generic name, class, description, and uses
- interactions - stores interaction pairs with severity, effects, and management advice

## Clinical Disclaimer

This tool is intended to support clinical decision making and demonstrate health informatics concepts. It does not replace professional medical judgment, official drug references, or consultation with a qualified pharmacist or physician.

## Research Context

This project was built as part of research into clinical decision support systems for low-resource healthcare settings in Sub-Saharan Africa, where access to comprehensive drug reference databases may be limited.

## Author

Emmanuel Owusu Adu
Computer Science Graduate | Health Informatics Researcher
Interests: Health Informatics, Information Systems, Information Science
<https://www.linkedin.com/in/emmanuel-owusu-adu-037084341>
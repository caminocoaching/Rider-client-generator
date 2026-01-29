
import os
from pypdf import PdfReader

files = [
    "Open ai FULL CONVERSATION SEQUENCES.pdf",
    "openAi GOOD DM EXAMPLES (HIGH RESPONSE RATE).pdf",
    "TONE CORRECTION FOR DMs_.pdf",
    "CREDIBILITY MARKERS TO REFERENCE.pdf"
]

for filename in files:
    if os.path.exists(filename):
        print(f"\n--- START {filename} ---")
        try:
            reader = PdfReader(filename)
            for page in reader.pages:
                print(page.extract_text())
        except Exception as e:
            print(f"Error reading {filename}: {e}")
        print(f"--- END {filename} ---\n")
    else:
        print(f"File not found: {filename}")

import os
from pypdf import PdfReader

files = [
    "Message templates.pdf",
    "Open ai FULL CONVERSATION SEQUENCES.pdf"
]

for filename in files:
    if os.path.exists(filename):
        print(f"\n--- START {filename} ---")
        try:
            reader = PdfReader(filename)
            for i, page in enumerate(reader.pages):
                try:
                    text = page.extract_text()
                    print(f"--- Page {i+1} ---")
                    print(text)
                except Exception as e:
                    print(f"Error reading page {i+1} in {filename}: {e}")
        except Exception as e:
            print(f"Error opening {filename}: {e}")
        print(f"--- END {filename} ---\n")
    else:
        print(f"File not found: {filename}")

import os
import glob
from pypdf import PdfReader

files = [
    "/Users/camino/Documents/Client Generator /Pipeline Messages and Follow ups .pdf"
]

for filename in files:
    print(f"\n================ START {filename} ================")
    try:
        reader = PdfReader(filename)
        for i, page in enumerate(reader.pages):
            try:
                print(f"--- Page {i+1} ---")
                text = page.extract_text(extraction_mode="layout")
                print(text)
            except Exception as e:
                print(f"Error reading page {i+1}: {e}")
    except Exception as e:
        print(f"Error opening file: {e}")
    print(f"================ END {filename} ================\n")

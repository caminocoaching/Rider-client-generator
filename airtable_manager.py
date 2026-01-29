import os
import streamlit as st
from pyairtable import Api
from typing import List, Dict, Optional
from datetime import datetime

class AirtableManager:
    """
    Manages interactions with the Airtable API for the Rider Pipeline.
    Handles fetching, upserting, and identity resolution (linking Social -> Email).
    """
    def __init__(self, api_key: str, base_id: str, table_name: str = "Riders"):
        self.api = Api(api_key)
        self.table_name = table_name
        self.table = self.api.table(base_id, table_name)
        # Cache for performance, though specifically for "fetch_all" operations
        self.riders_cache = []

    def fetch_all_riders(self) -> List[Dict]:
        """
        Fetches all records from Airtable.
        Returns a list of dictionaries (record fields + 'id').
        """
        try:
            # fetch_all returns a list of records: [{'id': 'rec...', 'createdTime': '...', 'fields': {...}}, ...]
            records = self.table.all()
            # Flatten for easier use in DataFrame later, but keep ID for updates
            clean_records = []
            for r in records:
                fields = r['fields']
                fields['id'] = r['id']  # Specific Airtable Record ID
                fields['createdTime'] = r['createdTime']
                clean_records.append(fields)
            
            self.riders_cache = clean_records
            return clean_records
        except Exception as e:
            st.error(f"Error fetching riders from Airtable: {e}")
            return []

    def upsert_rider(self, rider_data: Dict) -> bool:
        """
        Updates or Inserts a rider based on Identity Resolution logic.
        
        Logic:
        1. Try to match by EMAIL (if provided).
        2. If no email match (or input has no email), match by FULL NAME.
        3. If Match Found: Update existing record (Merge).
        4. If No Match: Create new record.
        """
        email = rider_data.get('Email')
        full_name = rider_data.get('Full Name')
        # 0. Auto-Generate Full Name if missing
        if not full_name and rider_data.get('First Name') and rider_data.get('Last Name'):
            full_name = f"{rider_data['First Name']} {rider_data['Last Name']}".strip()
            # Also add to payload so it syncs (if column exists/writable)
            rider_data['Full Name'] = full_name
            
        # 1. Prepare Payload & Search Keys
        search_email = email
        if search_email and search_email.startswith("no_email_"):
             search_email = None # Do NOT search by fake email

        # Retry loop for handling unknown fields
        max_retries = 5
        attempt = 0
        clean_data = {}
        for k, v in rider_data.items():
            if v is None: continue
            
            # Special Handling for "no_email_" placeholders
            # We do NOT want to send these to the "Email" column in Airtable as they might fail validation
            if k == 'Email' and isinstance(v, str) and v.startswith("no_email_"):
                continue
                
            clean_data[k] = v
        
        while attempt < max_retries:
            try:
                if not email and not full_name:
                    print("Skipping upsert: No Email or Full Name provided.")
                    return False
                
                existing_record = self._find_match(email, full_name)

                if existing_record:
                    # UPDATE
                    record_id = existing_record['id']
                    self.table.update(record_id, clean_data, typecast=True)
                    return True
                else:
                    # CREATE
                    self.table.create(clean_data, typecast=True)
                    return True
            
            except Exception as e:
                # Handle "Unknown field name" error from Airtable (422)
                # Error message usually looks like: ... 'Unknown field name: "Magic Link"' ...
                error_str = str(e)
                if "Unknown field name" in error_str:
                    import re
                    # Extract field name
                    match = re.search(r'Unknown field name: "(.*?)"', error_str)
                    if match:
                        bad_field = match.group(1)
                        print(f"Warning: Airtable rejected field '{bad_field}'. Removing and retrying.")
                        if bad_field in clean_data:
                            del clean_data[bad_field]
                            attempt += 1
                            continue
                
                # If not an unknown field error, or regex failed, stop and report.
                st.error(f"Error upserting rider to Airtable: {e}")
                return False
        
        return False

    def _find_match(self, email: Optional[str], full_name: Optional[str]) -> Optional[Dict]:
        """
        Finds an existing record in the cache (or refetches if critical? for now use cache or direct formula search).
        Using direct formula search is safer for consistency but slower. 
        Given the likely dataset size (<10k), fetching all or formula search is fine.
        Let's use formula for precision.
        """
        # 1. Search by Email
        if email:
            # Airtable formula: {Email} = 'foo@bar.com'
            matches = self.table.all(formula=f"{{Email}} = '{email}'", max_records=1)
            if matches:
                return matches[0]

        # 2. Search by Name (if Email didn't find anything or wasn't provided)
        if full_name:
            # Airtable formula: {Full Name} = 'John Doe'
            # Note: exact match. Fuzzy matching requires client-side logic (fetching all).
            matches = self.table.all(formula=f"{{Full Name}} = '{full_name}'", max_records=1)
            if matches:
                return matches[0]

        return None

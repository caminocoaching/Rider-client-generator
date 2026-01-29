    def _load_from_airtable(self):
        """Load Master Records from Airtable"""
        if not self.airtable: return
        
        # Check cache or fetch
        if self.airtable.riders_cache:
            records = self.airtable.riders_cache
        else:
            records = self.airtable.fetch_all_riders()
            
        print(f"Loaded {len(records)} riders from Airtable")
        
        for r in records:
            # Identity
            email = r.get('Email')
            full_name = r.get('Full Name')
            
            rider_email = email
            if not rider_email and full_name:
                # Slugify name for ID
                slug = full_name.lower().strip().replace(' ', '_')
                slug = "".join([c for c in slug if c.isalnum() or c == '_'])
                if not slug: slug = "unknown_rider"
                rider_email = slug
            
            if not rider_email: continue
            
            rider_email = rider_email.strip()
            
            # Name parts
            first = r.get('First Name')
            last = r.get('Last Name')
            if not first and full_name:
                 parts = full_name.split(' ')
                 first = parts[0]
                 if len(parts) > 1: last = " ".join(parts[1:])
            
            rider = self._get_or_create_rider(rider_email, first or "", last or "")
            
            # Map Fields
            if r.get('Phone'): rider.phone = r.get('Phone')
            if r.get('FB URL'): rider.facebook_url = r.get('FB URL')
            if r.get('IG URL'): rider.instagram_url = r.get('IG URL')
            if r.get('Magic Link'): rider.magic_link = r.get('Magic Link')
            
            # Tags (Airtable sends list of strings)
            tags = r.get('Tags')
            if tags and isinstance(tags, list):
                rider.tags = ",".join(tags) # Store as CSV string for compatibility
            
            # Scores (Day 1)
            if r.get('Overall Score'): rider.day1_score = float(r.get('Overall Score'))
            if r.get('Biggest Mistake'): rider.biggest_mistake = r.get('Biggest Mistake')
            
            # Dates
            if r.get('Date Joined'): rider.outreach_date = self._parse_date(r.get('Date Joined'))
            if r.get('Date Day 1'): rider.day1_date = self._parse_date(r.get('Date Day 1'))
            # ... add others as needed
            
            # Stage Mapping
            stage_str = r.get('Stage')
            if stage_str:
                s_clean = stage_str.strip().lower()
                found_stage = None
                for stage in FunnelStage:
                    if stage.value.lower() == s_clean:
                        found_stage = stage
                        break
                    # Aliases
                    if s_clean in ['messaged', 'outreach']: found_stage = FunnelStage.MESSAGED
                    if s_clean in ['client', 'won']: found_stage = FunnelStage.CLIENT
                    if s_clean in ['lost', 'not a fit']: found_stage = FunnelStage.NOT_A_FIT
                    if s_clean in ['registered', 'blueprint started']: found_stage = FunnelStage.BLUEPRINT_STARTED

                if found_stage:
                    rider.current_stage = found_stage


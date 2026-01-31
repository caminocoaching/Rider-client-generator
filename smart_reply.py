import pandas as pd
import os
from difflib import SequenceMatcher

class SmartReplyManager:
    def __init__(self, data_dir, rider_db=None):
        """Initialize SmartReplyManager with data directory and optional rider database."""
        self.data_dir = data_dir
        self.history_file = os.path.join(data_dir, "Facebook Messenger History - Sheet1 (1).csv")
        self.pairs = [] # List of {'trigger': str, 'reply': str, 'confidence': float, 'outcome': str}
        self.winning_senders = set()
        
        # Pre-process winners if DB provided
        if rider_db:
             self._identify_winners(rider_db)
             
        self.load_history()

    def _identify_winners(self, rider_db):
        """Builds a set of names/emails responsible for Sales/Client status."""
        try:
            # Check if dict or dataframe
            if isinstance(rider_db, dict):
                riders = rider_db.values()
            else:
                return 

            for r in riders:
                # Check for "Client" or "Sale" in stage
                # Robustly handle enum or string
                stage_str = str(r.current_stage.value).lower() if hasattr(r.current_stage, 'value') else str(r.current_stage).lower()
                
                if "client" in stage_str or "sale" in stage_str or "booked" in stage_str:
                    # Add variations of name to match Messenger
                    self.winning_senders.add(r.full_name)
                    if r.facebook_url:
                        # Extract username/id if possible? Hard. 
                        # Just rely on Full Name for now as Messenger export usually has names.
                        pass
            
            print(f"Identified {len(self.winning_senders)} winning riders.")
            
        except Exception as e:
            print(f"Error identifying winners: {e}")

    def load_history(self):
        """Loads the CSV and extracts Prospect -> Craig conversation pairs."""
        if not os.path.exists(self.history_file):
            print(f"History file not found: {self.history_file}")
            return

        try:
            # Load with headers on row 1 (0-indexed) as per inspection
            df = pd.read_csv(self.history_file, header=1)
            
            # Filter relevant columns
            if 'thread_path' not in df.columns:
                return

            threads = df.groupby('thread_path')
            
            for thread_id, group in threads:
                # Sort by time
                group = group.sort_values('messages__timestamp_ms')
                
                rows = group.to_dict('records')
                
                # Check if this thread involves a winner
                # We need to find the OTHER person in the thread.
                # Usually group['messages__sender_name'].unique() has 2 names.
                participants = group['messages__sender_name'].unique()
                is_winning_thread = False
                for p in participants:
                    if str(p) in self.winning_senders:
                        is_winning_thread = True
                        break
                
                for i in range(len(rows) - 1):
                    current_msg = rows[i]
                    next_msg = rows[i+1]
                    
                    sender = str(current_msg.get('messages__sender_name', ''))
                    content = str(current_msg.get('messages__content', ''))
                    
                    next_sender = str(next_msg.get('messages__sender_name', ''))
                    next_content = str(next_msg.get('messages__content', ''))
                    
                    # Logic: 
                    # If CURRENT is NOT Craig AND NEXT IS Craig -> Valid Pair
                    if "Craig Muirhead" not in sender and "Craig Muirhead" in next_sender:
                        # Ensure content is valid text
                        if len(content) > 3 and len(next_content) > 3:
                            self.pairs.append({
                                'trigger': content,
                                'reply': next_content,
                                'original_sender': sender,
                                'date': next_msg.get('messages__timestamp_ms'),
                                'is_winning': is_winning_thread
                            })
                            
            print(f"Loaded {len(self.pairs)} conversation pairs for Smart Reply.")
            
        except Exception as e:
            print(f"Error loading smart reply history: {e}")

    def find_reply(self, input_text, threshold=0.4):
        """Finds the best matching reply for the given input text."""
        if not input_text or not self.pairs:
            return None

        best_match = None
        best_ratio = 0.0

        for pair in self.pairs:
            # similarity ratio
            ratio = SequenceMatcher(None, input_text, pair['trigger']).ratio()
            
            # Boost logic for winning replies?
            # Let's say we value a winning reply slightly more if it matches well.
            # But we don't want to return garbage just because it's a winner.
            # Let's just store the best match based on text, but return metadata.
            # Alternatively: distinct search for winners vs others? 
            # Simple approach: Text match is king, but we flag it.
            
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = pair

        if best_ratio >= threshold:
            # Return match with metadata
            return {
                'reply': best_match['reply'],
                'confidence': best_ratio,
                'trigger_matched': best_match['trigger'],
                'sender': best_match['original_sender'],
                'is_winning': best_match.get('is_winning', False),
                'date': best_match.get('date', 0)
            }
        
        return None

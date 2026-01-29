import pandas as pd
import os
from difflib import SequenceMatcher

class SmartReplyManager:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.history_file = os.path.join(data_dir, "Facebook Messenger History - Sheet1 (1).csv")
        self.pairs = [] # List of {'trigger': str, 'reply': str, 'confidence': float}
        self.load_history()

    def load_history(self):
        """Loads the CSV and extracts Prospect -> Craig conversation pairs."""
        if not os.path.exists(self.history_file):
            print(f"History file not found: {self.history_file}")
            return

        try:
            # Load with headers on row 1 (0-indexed) as per inspection
            df = pd.read_csv(self.history_file, header=1)
            
            # Filter relevant columns
            # We need: 'messages__sender_name', 'messages__content', 'thread_path', 'messages__timestamp_ms'
            # Note: Timestamp might need parsing if sorting is required, but let's assume chronological per thread group is implied or manageable.
            
            # 1. Group by Thread
            # 'thread_path' identifies the conversation. 'title' is also useful.
            if 'thread_path' not in df.columns:
                return

            threads = df.groupby('thread_path')
            
            for thread_id, group in threads:
                # Sort by time
                group = group.sort_values('messages__timestamp_ms')
                
                rows = group.to_dict('records')
                
                for i in range(len(rows) - 1):
                    current_msg = rows[i]
                    next_msg = rows[i+1]
                    
                    sender = str(current_msg.get('messages__sender_name', ''))
                    content = str(current_msg.get('messages__content', ''))
                    
                    next_sender = str(next_msg.get('messages__sender_name', ''))
                    next_content = str(next_msg.get('messages__content', ''))
                    
                    # Logic: 
                    # If CURRENT is NOT Craig AND NEXT IS Craig -> Valid Pair
                    # 'Craig Muirhead' is the user name usually.
                    
                    if "Craig Muirhead" not in sender and "Craig Muirhead" in next_sender:
                        # Ensure content is valid text
                        if len(content) > 3 and len(next_content) > 3:
                            self.pairs.append({
                                'trigger': content,
                                'reply': next_content,
                                'original_sender': sender,
                                'date': next_msg.get('messages__timestamp_ms')
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
            
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = pair

        if best_ratio >= threshold:
            # Return match with metadata
            return {
                'reply': best_match['reply'],
                'confidence': best_ratio,
                'trigger_matched': best_match['trigger'],
                'sender': best_match['original_sender']
            }
        
        return None

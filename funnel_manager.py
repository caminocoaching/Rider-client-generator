#!/usr/bin/env python3
"""
Camino Coaching Funnel Manager
==============================
A comprehensive sales funnel management tool for tracking riders through
the Podium Contenders Blueprint program.

Target: £15,000 monthly revenue
Programme Price: £4,000 (with payment plan options)

Funnel Stages:
- Phase 1: Outreach (Email, Facebook DM, Instagram DM)
- Phase 2: Registration for 3-day free training + Day 1 Assessment
- Phase 3: Day 2 Self-Assessment + Day 3 Strategy Call Booking

Author: Camino Coaching
"""

import csv
import json
import random
import pandas as pd
import os
import os
import streamlit as st
import gsheets_loader
from airtable_manager import AirtableManager
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from collections import defaultdict
import re


# =============================================================================
# CONFIGURATION
# =============================================================================

class FunnelConfig:
    """Central configuration for funnel targets and rates"""

    # Revenue targets
    MONTHLY_REVENUE_TARGET = 15000  # £15,000
    PROGRAMME_PRICE = 4000  # £4,000 full price

    # Average effective price (accounting for payment plans)
    # This can be adjusted based on actual payment plan mix
    AVERAGE_DEAL_VALUE = 4000

    # Working days
    WORKING_DAYS_PER_WEEK = 5
    WEEKS_PER_MONTH = 4

    # Historical conversion rates (to be calibrated with actual data)
    # These are starting estimates - the system will learn from your data
    DEFAULT_CONVERSION_RATES = {
        'outreach_to_registration': 0.08,      # 8% of outreach becomes registrations
        'registration_to_day1': 0.70,          # 70% complete Day 1 assessment
        'day1_to_day2': 0.60,                  # 60% complete Day 2 assessment
        'day2_to_strategy_call': 0.40,         # 40% book strategy call
        'strategy_call_to_sale': 0.25,         # 25% of calls convert to sale
    }

    # Rescue message timing (hours after drop-off)
    RESCUE_TIMING = {
        'registration_no_day1': 24,     # 24 hours after registration
        'day1_no_day2': 24,             # 24 hours after Day 1
        'day2_no_call': 12,             # 12 hours after Day 2 (urgency)
    }


class OutreachChannel(Enum):
    EMAIL = "email"
    FACEBOOK_DM = "facebook_dm"
    INSTAGRAM_DM = "instagram_dm"


class FunnelStage(Enum):
    CONTACT = "Contact"
    MESSAGED = "Messaged"
    REPLIED = "Replied"
    RACE_WEEKEND = "Race Weekend"
    LINK_SENT = "Link Sent"
    BLUEPRINT_STARTED = "Podium Contenders Blueprint Started"
    DAY1_COMPLETE = "Day 1 Completed"
    DAY2_COMPLETE = "Day 2 Completed"
    STRATEGY_CALL_BOOKED = "Strategy Call Booked"
    CLIENT = "Client"
    NOT_A_FIT = "Not a good fit"
    FOLLOW_UP = "Follow up"
    FLOW_PROFILE_COMPLETED = "Flow Profile Completed"
    MINDSET_QUIZ_COMPLETED = "Mindset Quiz Completed"
    SLEEP_TEST_COMPLETED = "Sleep Test Completed"
    NO_SOCIALS = "No Socials Found"
    
    # Legacy / Compatibility Aliases
    OUTREACH = "Messaged"
    REGISTERED = "Podium Contenders Blueprint Started"
    SALE_CLOSED = "Client"
    NO_SALE = "Not a good fit"
    
    # Old ones kept for CSV capability until migrated
    RACE_REVIEW_COMPLETE = "Race Weekend Review Completed"
    SEASON_REVIEW_SENT = "End of Season Review Link Sent"
    SEASON_REVIEW_COMPLETE = "End of Season Review Completed"
    BLUEPRINT_LINK_SENT = "Blueprint Link Sent"



# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Rider:
    """Represents a rider in the funnel"""
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None

    # Funnel tracking
    outreach_channel: Optional[OutreachChannel] = None
    outreach_date: Optional[datetime] = None

    # Funnel progress
    current_stage: FunnelStage = FunnelStage.CONTACT
    
    # Dates
    registered_date: Optional[datetime] = None
    day1_complete_date: Optional[datetime] = None
    day2_complete_date: Optional[datetime] = None
    strategy_call_booked_date: Optional[datetime] = None
    strategy_call_complete_date: Optional[datetime] = None
    sale_closed_date: Optional[datetime] = None
    
    # Social Links
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    championship: Optional[str] = None
    
    # Review Dates & Status
    race_weekend_review_date: Optional[datetime] = None
    race_weekend_review_status: str = "pending" # pending, completed
    end_of_season_review_date: Optional[datetime] = None
    # Scores
    day1_score: Optional[float] = None
    day2_scores: Optional[Dict[str, float]] = None
    
    # Flow Profile (Lead Magnet)
    flow_profile_date: Optional[datetime] = None
    flow_profile_score: Optional[float] = None
    flow_profile_result: Optional[str] = None
    flow_profile_url: Optional[str] = None

    # Sleep Test (Lead Magnet)
    sleep_test_date: Optional[datetime] = None
    sleep_score: Optional[float] = None
    
    # Mindset Quiz (Lead Magnet)
    mindset_quiz_date: Optional[datetime] = None
    mindset_score: Optional[float] = None
    mindset_result: Optional[str] = None # e.g. "Fixed Mindset", "Growth Mindset"

    # Rescue tracking
    rescue_messages_sent: List[str] = field(default_factory=list)
    last_rescue_date: Optional[datetime] = None

    # Enhanced CRM Fields
    championship: Optional[str] = None
    notes: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    is_disqualified: bool = False
    disqualification_reason: Optional[str] = None
    sale_value: Optional[float] = None



    payment_plan: bool = False
    monthly_payment: Optional[float] = None

    # Metadata
    country: Optional[str] = None
    rider_type: Optional[str] = None
    championship: Optional[str] = None

    @property
    def full_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name if name else self.email

    @property
    def days_in_current_stage(self) -> int:
        """Calculate days since entering current stage"""
        stage_dates = {
            FunnelStage.OUTREACH: self.outreach_date,
            FunnelStage.REGISTERED: self.registered_date,
            FunnelStage.DAY1_COMPLETE: self.day1_complete_date,
            FunnelStage.DAY2_COMPLETE: self.day2_complete_date,
            FunnelStage.STRATEGY_CALL_BOOKED: self.strategy_call_booked_date,
        }

        stage_date = stage_dates.get(self.current_stage)
        if stage_date:
            return (datetime.now() - stage_date).days
        return 0

    def needs_rescue(self, config: FunnelConfig = FunnelConfig()) -> Tuple[bool, str]:
        """Check if rider needs a rescue message"""
        now = datetime.now()

        # Registered but no Day 1
        if self.current_stage == FunnelStage.REGISTERED and self.registered_date:
            hours_since = (now - self.registered_date).total_seconds() / 3600
            if hours_since >= config.RESCUE_TIMING['registration_no_day1']:
                if 'day1_rescue' not in self.rescue_messages_sent:
                    return True, 'day1_rescue'

        # Day 1 complete but no Day 2
        if self.current_stage == FunnelStage.DAY1_COMPLETE and self.day1_complete_date:
            hours_since = (now - self.day1_complete_date).total_seconds() / 3600
            if hours_since >= config.RESCUE_TIMING['day1_no_day2']:
                if 'day2_rescue' not in self.rescue_messages_sent:
                    return True, 'day2_rescue'

        # Day 2 complete but no strategy call
        if self.current_stage == FunnelStage.DAY2_COMPLETE and self.day2_complete_date:
            hours_since = (now - self.day2_complete_date).total_seconds() / 3600
            if hours_since >= config.RESCUE_TIMING['day2_no_call']:
                if 'strategy_call_rescue' not in self.rescue_messages_sent:
                    return True, 'strategy_call_rescue'

        return False, ''


@dataclass
class DailyMetrics:
    """Daily funnel metrics"""
    date: datetime

    # Outreach counts by channel
    outreach_email: int = 0
    outreach_facebook: int = 0
    outreach_instagram: int = 0

    # Funnel progression
    new_registrations: int = 0
    day1_completions: int = 0
    day2_completions: int = 0
    strategy_calls_booked: int = 0
    strategy_calls_completed: int = 0
    sales_closed: int = 0

    # Revenue
    revenue_closed: float = 0.0
    monthly_recurring_added: float = 0.0

    # Rescue activity
    rescue_messages_sent: int = 0
    rescue_conversions: int = 0

    @property
    def total_outreach(self) -> int:
        return self.outreach_email + self.outreach_facebook + self.outreach_instagram

    @property
    def outreach_to_registration_rate(self) -> float:
        if self.total_outreach == 0:
            return 0.0
        return self.new_registrations / self.total_outreach


@dataclass
class FunnelTargets:
    """Weekly and monthly targets"""

    # Monthly targets
    monthly_revenue: float
    monthly_sales: int
    monthly_strategy_calls: int
    monthly_day2_completions: int
    monthly_day1_completions: int
    monthly_registrations: int
    monthly_outreach: int

    # Weekly targets (monthly / 4)
    weekly_revenue: float = 0
    weekly_sales: int = 0
    weekly_strategy_calls: int = 0
    weekly_day2_completions: int = 0
    weekly_day1_completions: int = 0
    weekly_registrations: int = 0
    weekly_outreach: int = 0

    # Daily targets (weekly / 5 working days)
    daily_outreach: int = 0

    def __post_init__(self):
        self.weekly_revenue = self.monthly_revenue / 4
        self.weekly_sales = max(1, self.monthly_sales // 4)
        self.weekly_strategy_calls = max(1, self.monthly_strategy_calls // 4)
        self.weekly_day2_completions = max(1, self.monthly_day2_completions // 4)
        self.weekly_day1_completions = max(1, self.monthly_day1_completions // 4)
        self.weekly_registrations = max(1, self.monthly_registrations // 4)
        self.weekly_outreach = max(1, self.monthly_outreach // 4)
        self.daily_outreach = max(1, self.weekly_outreach // 5)


# =============================================================================
# FUNNEL CALCULATOR
# =============================================================================

class FunnelCalculator:
    """Calculate required activities to hit revenue targets"""

    def __init__(self, config: FunnelConfig = None):
        self.config = config or FunnelConfig()
        self.conversion_rates = dict(self.config.DEFAULT_CONVERSION_RATES)

    def update_conversion_rates(self, rates: Dict[str, float]):
        """Update conversion rates based on actual data"""
        self.conversion_rates.update(rates)

    def calculate_targets(self,
                         monthly_revenue_target: float = None,
                         average_deal_value: float = None) -> FunnelTargets:
        """
        Work backwards from revenue target to calculate required activities.

        Revenue Target → Sales Needed → Strategy Calls → Day 2 → Day 1 → Registrations → Outreach
        """
        revenue_target = monthly_revenue_target or self.config.MONTHLY_REVENUE_TARGET
        deal_value = average_deal_value or self.config.AVERAGE_DEAL_VALUE

        # Work backwards through the funnel
        sales_needed = int(revenue_target / deal_value) + 1

        strategy_calls_needed = int(
            sales_needed / self.conversion_rates['strategy_call_to_sale']
        ) + 1

        day2_needed = int(
            strategy_calls_needed / self.conversion_rates['day2_to_strategy_call']
        ) + 1

        day1_needed = int(
            day2_needed / self.conversion_rates['day1_to_day2']
        ) + 1

        registrations_needed = int(
            day1_needed / self.conversion_rates['registration_to_day1']
        ) + 1

        outreach_needed = int(
            registrations_needed / self.conversion_rates['outreach_to_registration']
        ) + 1

        return FunnelTargets(
            monthly_revenue=revenue_target,
            monthly_sales=sales_needed,
            monthly_strategy_calls=strategy_calls_needed,
            monthly_day2_completions=day2_needed,
            monthly_day1_completions=day1_needed,
            monthly_registrations=registrations_needed,
            monthly_outreach=outreach_needed
        )

    def forecast_revenue(self,
                        current_outreach: int,
                        current_registrations: int,
                        current_day1: int,
                        current_day2: int,
                        current_calls: int) -> Dict[str, float]:
        """
        Forecast expected revenue based on current funnel state.
        """
        # Project forward through funnel
        projected_registrations = current_outreach * self.conversion_rates['outreach_to_registration']
        projected_day1 = (current_registrations + projected_registrations) * self.conversion_rates['registration_to_day1']
        projected_day2 = (current_day1 + projected_day1) * self.conversion_rates['day1_to_day2']
        projected_calls = (current_day2 + projected_day2) * self.conversion_rates['day2_to_strategy_call']
        projected_sales = (current_calls + projected_calls) * self.conversion_rates['strategy_call_to_sale']
        projected_revenue = projected_sales * self.config.AVERAGE_DEAL_VALUE

        return {
            'projected_registrations': projected_registrations,
            'projected_day1': projected_day1,
            'projected_day2': projected_day2,
            'projected_calls': projected_calls,
            'projected_sales': projected_sales,
            'projected_revenue': projected_revenue
        }


# =============================================================================
# RESCUE MESSAGE SYSTEM
# =============================================================================

class RescueMessageManager:
    """Manages rescue messages for riders who have dropped out"""

    TEMPLATES = {
        'day1_rescue': {
            'subject': "You started something amazing - let's not leave it unfinished",
            'email': """Hi {first_name},

I noticed you registered for the Podium Contenders Blueprint but haven't completed Day 1's training yet - "The 7 Biggest Mental Mistakes Costing You Lap Time".

Look, I get it. Life gets busy. Racing prep takes priority.

But here's the thing - this 20-minute assessment could be the most valuable thing you do for your racing this week.

Why? Because you can't fix what you can't see.

The riders who've gone through this tell me they finally understand WHY they've been leaving time on the table. And that clarity? It's the first step to unlocking your real potential.

Your spot is still waiting: [LINK]

See you on the other side,
{coach_name}

P.S. The assessment reveals your score across all 7 mental mistake categories. Most riders are shocked by what they discover about themselves.""",
            'dm': """Hey {first_name}! 👋

Noticed you signed up for the Podium Contenders Blueprint but haven't done Day 1 yet.

The 7 Biggest Mistakes assessment only takes 20 mins and riders are telling me it's been a game-changer for understanding where they're leaving time on track.

Your link's still active - want me to resend it?

Let me know if you have any questions!"""
        },

        'day2_rescue': {
            'subject': "Day 2 unlocks your racing potential - don't stop now",
            'email': """Hi {first_name},

You crushed Day 1 of the Podium Contenders Blueprint. Your 7 Biggest Mistakes assessment revealed some powerful insights about your mental game.

But here's the thing - Day 1 shows you the PROBLEM. Day 2 shows you the SOLUTION.

The 5-Pillar Self-Assessment takes what you learned yesterday and maps out exactly where to focus your energy for maximum improvement.

Without it, you've got half the picture.

Don't leave your breakthrough incomplete: [LINK]

This won't take long, and the clarity you'll get is worth every minute.

Talk soon,
{coach_name}

P.S. Riders who complete both assessments before their Strategy Call see 3x better results in their first month of training. Just saying... 🏁""",
            'dm': """Hey {first_name}!

Loved seeing your Day 1 results - some really interesting patterns there.

Day 2's 5-Pillar Assessment is where it all comes together though. It shows you exactly which areas will give you the biggest gains.

Takes about 15 mins - you ready to dive in?

Here's your link: [LINK]"""
        },

        'strategy_call_rescue': {
            'subject': "Your Strategy Call spot is waiting (but not for long)",
            'email': """Hi {first_name},

You've done the work. You completed both assessments. You KNOW where your mental game needs attention.

But knowledge without action? That's just entertainment.

The Strategy Call is where we turn your insights into a real plan. Where we look at your specific situation, your goals, and map out exactly how to get there.

I've got a few spots open this week: [BOOKING LINK]

This isn't a sales pitch. It's a genuine conversation about your racing and whether we're a good fit to work together.

If we are? Great. If not? You'll still walk away with actionable insights you can use immediately.

But you've got to book the call to find out.

Ready when you are,
{coach_name}

P.S. These spots fill up fast. If you're serious about transforming your racing this season, don't wait.""",
            'dm': """Hey {first_name}!

You've done Day 1 AND Day 2 - that's awesome! You're clearly serious about this.

The next step is a Strategy Call where we look at your results together and figure out the best path forward for you.

No pressure, no hard sell - just a real conversation about your racing goals.

I've got some spots open - shall I send the booking link?"""
        }
    }

    def __init__(self):
        self.coach_name = "Camino"  # Configure this

    def get_rescue_message(self,
                          rescue_type: str,
                          rider: Rider,
                          channel: str = 'email') -> Dict[str, str]:
        """Generate a personalized rescue message"""
        template = self.TEMPLATES.get(rescue_type, {})

        if channel == 'email':
            return {
                'subject': template.get('subject', '').format(
                    first_name=rider.first_name
                ),
                'body': template.get('email', '').format(
                    first_name=rider.first_name,
                    coach_name=self.coach_name
                )
            }
        else:
            return {
                'body': template.get('dm', '').format(
                    first_name=rider.first_name,
                    coach_name=self.coach_name
                )
            }

    def get_riders_needing_rescue(self, riders: List[Rider]) -> Dict[str, List[Rider]]:
        """Identify all riders needing rescue messages"""
        rescue_needed = {
            'day1_rescue': [],
            'day2_rescue': [],
            'strategy_call_rescue': []
        }

        for rider in riders:
            needs_rescue, rescue_type = rider.needs_rescue()
            if needs_rescue:
                rescue_needed[rescue_type].append(rider)

        return rescue_needed


class FollowUpMessageManager:
    """Generates next-step messages based on funnel state"""

    def __init__(self):
        self.coach_name = "Camino"

    def get_message(self, rider: Rider) -> Optional[Dict[str, str]]:
        stage = rider.current_stage
        
        # 1. Registered -> Day 1 (Nudge)
        if stage == FunnelStage.REGISTERED:
            return {
                "subject": "Ready to fix the #1 mistake?",
                "body": (
                    f"Hey {rider.first_name},\n\n"
                    "Saw you registered for the blueprint but haven't started Day 1 yet.\n\n"
                    "The first video covers the biggest mistake most riders make with their prep "
                    "(and why they plateau). Takes about 15 mins.\n\n"
                    "Here's the link to jump in: [LINK]\n\n"
                    "Let me know if you have any questions before you start."
                )
            }
            
        # 2. Day 1 -> Day 2
        elif stage == FunnelStage.DAY1_COMPLETE:
            return {
                "subject": "Your Day 1 assessment results",
                "body": (
                    f"Hey {rider.first_name},\n\n"
                    f"Just reviewed your Day 1 assessment. You scored {rider.day1_score}/100.\n\n"
                    "That's a solid starting point, but definitely some low-hanging fruit to improve performance.\n\n"
                    "Day 2 is about building your Self-Assessment profile. That's where we get specific on exactly "
                    "WHICH mental blockers are slowing you down.\n\n"
                    "Ready for the next step? [LINK]"
                )
            }

        # 3. Flow Profile / Post Season Logic (Special Cases)
        
        # TEMPLATE: SEQUENCE 3 (Post-Season Review Follow-up)
        if rider.end_of_season_review_date and stage != FunnelStage.STRATEGY_CALL_BOOKED:
             return {
                 "subject": "Your 2025 Season Review",
                 "body": (
                     f"{rider.first_name} - saw you completed the post-season review.\n\n"
                     "That's actually the #1 thing that separates mid-pack riders from championship contenders. "
                     "Most riders ignore it all off-season and then wonder why 2026 feels like 2025 all over again.\n\n"
                     "Want me to show you how to fix the gaps you identified?"
                 )
             }

        # TEMPLATE: SEQUENCE 2 (Off-Season Reflection -> Call)
        if stage == FunnelStage.OUTREACH:
            return {
                "subject": "2026 Season Prep",
                "body": (
                    f"{rider.first_name} - now that the 2025 season's wrapped, what's the one thing you wish you'd worked on before it started?\n\n"
                    "Most riders say 'mental game' in December and then show up to testing in February with the same issues.\n\n"
                    "If you're serious about making 2026 different, I'm doing some 1-on-1 calls to build proper off-season game plans. Up for a chat?"
                )
            }
            
        # 4. Old Flow Profile Logic (Fallback)
        if rider.flow_profile_result:
             result_type = rider.flow_profile_result
             return {
                "subject": f"Your Flow Profile: {result_type}",
                "body": (
                    f"Hey {rider.first_name},\n\n"
                    f"I saw you got '{result_type}' on your Flow Profile.\n\n"
                    "This usually means you have natural speed but struggle with consistency (or vice versa).\n\n"
                    "We have a specific protocol for this profile. Want me to send over the details?"
                )
             }

        return None


# =============================================================================
# MANUAL DAILY STATS
# =============================================================================

@dataclass
class DailyManualStats:
    """Manual daily inputs for metrics not tracked automatically"""
    date: datetime.date
    fb_messages_sent: int = 0
    ig_messages_sent: int = 0
    links_sent: int = 0

class DailyStatsManager:
    """Manages manual daily statistics"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.filename = "daily_stats.csv"
        self.stats: Dict[datetime.date, DailyManualStats] = {}
        self._load_stats()
        
    def _load_stats(self):
        """Load stats from CSV"""
        filepath = os.path.join(self.data_dir, self.filename)
        if not os.path.exists(filepath):
            return
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_str = row.get('date')
                    if not date_str:
                        continue
                    dt = datetime.strptime(date_str, '%Y-%m-%d').date()
                    
                    self.stats[dt] = DailyManualStats(
                        date=dt,
                        fb_messages_sent=int(row.get('fb_messages_sent', 0)),
                        ig_messages_sent=int(row.get('ig_messages_sent', 0)),
                        links_sent=int(row.get('links_sent', 0))
                    )
        except Exception as e:
            print(f"Error loading daily stats: {e}")

    def save_stats(self, date: datetime.date, fb: int, ig: int, links: int):
        """Save stats for a specific date"""
        self.stats[date] = DailyManualStats(
            date=date,
            fb_messages_sent=fb,
            ig_messages_sent=ig,
            links_sent=links
        )
        
        # Rewrite file
        filepath = os.path.join(self.data_dir, self.filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['date', 'fb_messages_sent', 'ig_messages_sent', 'links_sent'])
            writer.writeheader()
            
            # Sort by date
            for dt in sorted(self.stats.keys()):
                s = self.stats[dt]
                writer.writerow({
                    'date': dt.strftime('%Y-%m-%d'),
                    'fb_messages_sent': s.fb_messages_sent,
                    'ig_messages_sent': s.ig_messages_sent,
                    'links_sent': s.links_sent
                })

    def get_stats_for_date(self, date: datetime.date) -> DailyManualStats:
        return self.stats.get(date, DailyManualStats(date=date))

    def get_mtd_stats(self, year: int, month: int) -> Dict[str, int]:
        """Get Month-To-Date totals"""
        total_fb = 0
        total_ig = 0
        total_links = 0
        
        for dt, s in self.stats.items():
            if dt.year == year and dt.month == month:
                total_fb += s.fb_messages_sent
                total_ig += s.ig_messages_sent
                total_links += s.links_sent
                
        return {
            'fb_messages_sent': total_fb,
            'ig_messages_sent': total_ig,
            'links_sent': total_links
        }

    def update_stats(self, date: datetime.date, **kwargs):
        """Update specific stats for a date"""
        current = self.get_stats_for_date(date)
        
        # Current values
        fb = current.fb_messages_sent
        ig = current.ig_messages_sent
        links = current.links_sent
        
        # Update from kwargs (additive)
        if 'fb_messages_sent' in kwargs:
            fb += kwargs['fb_messages_sent']
        if 'ig_messages_sent' in kwargs:
            ig += kwargs['ig_messages_sent']
        if 'links_sent' in kwargs:
            links += kwargs['links_sent']
            
        self.save_stats(date, fb, ig, links)

    def increment_fb(self):
        """Add +1 to Today's FB Messages"""
        self.update_stats(datetime.now().date(), fb_messages_sent=1)
        
    def increment_ig(self):
        """Add +1 to Today's IG Messages"""
        self.update_stats(datetime.now().date(), ig_messages_sent=1)
        
    def increment_link(self):
        """Add +1 to Today's Links Sent"""
        self.update_stats(datetime.now().date(), links_sent=1)

    def get_mtd_total(self, stat_name: str) -> int:
        """Calculate Month-To-Date total for a manual stat"""
        now = datetime.now()
        stats = self.get_mtd_stats(now.year, now.month)
        return stats.get(stat_name, 0)


# =============================================================================
# DATA LOADER
# =============================================================================

class DataLoader:
    """Load and process data from CSV files"""

    def __init__(self, data_dir: str, overrides: Optional[Dict[str, Any]] = None):
        self.data_dir = data_dir
        self.riders: Dict[str, Rider] = {}
        self.load_report = {'total': 0, 'loaded': 0, 'skipped': 0, 'reasons': {}}
        self.overrides = overrides or {}
        
        # Initialize Airtable Manager
        self.airtable = None
        if "airtable" in st.secrets:
             try:
                 self.airtable = AirtableManager(
                     api_key=st.secrets["airtable"]["api_key"],
                     base_id=st.secrets["airtable"]["base_id"],
                     table_name=st.secrets["airtable"].get("table_name", "Riders")
                 )
                 print("Airtable Manager Initialized")
             except Exception as e:
                 print(f"Failed to init Airtable: {e}")
                 self.airtable = None
        else:
             print("Airtable secrets not found.")

    def load_all_data(self) -> Dict[str, Rider]:
        """Load data from all CSV files and merge into rider records"""

        # 1. Load Master Data from Airtable (Moved to END to act as Source of Truth)
        # self._load_from_airtable()

        # Load each data source
        self._load_strategy_call_applications()
        self._load_blueprint_registrations()
        self._load_day1_assessments()
        self._load_day2_assessments()
        self._load_xperiencify_csv()
        self._load_flow_profile_results()
        self._load_sleep_test()
        self._load_sleep_test()
        self._load_mindset_quiz()
        self._load_race_reviews()
        
        # Load manual updates LAST (overrides)
        self._load_manual_updates()
        self._load_revenue_log()
        self._load_rider_details()
        
        # Load centralized Rider Database (Contact Info Source of Truth)
        self._load_rider_database()
        
        # Scan for reviews/socials (flexible CSVs)
        self._scan_for_social_and_reviews()
        
        # Load Facebook History (New)
        self._load_facebook_history()

        # --- FINAL OVERRIDE: AIRTABLE (Source of Truth for Cloud) ---
        self._load_from_airtable()

        return self.riders


    def _get_data_iter(self, filename: str):
        """
        Yields rows (dicts) from either overrides or filesystem.
        Normalizes all keys to lowercase to handle Google Sheets vs CSV differences.
        """
        raw_iter = None
        
        # 1. Check overrides (support DataFrame or list of dicts)
        if filename in self.overrides:
            data = self.overrides[filename]
            # If it's a DataFrame (has 'to_dict'), convert it
            if hasattr(data, 'to_dict'):
                # orient='records' -> list of dicts
                raw_iter = data.to_dict(orient='records')
            elif isinstance(data, list):
                raw_iter = data
        
        # 2. File System fallback
        elif os.path.exists(os.path.join(self.data_dir, filename)):
            try:
                # Read into list to allow safe iteration logic
                with open(os.path.join(self.data_dir, filename), 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    raw_iter = list(reader)
            except Exception as e:
                print(f"Error reading {filename}: {e}")
                return

        if raw_iter:
            for row in raw_iter:
                # Normalize keys: Lowercase and strip
                clean_row = {str(k).lower().strip(): v for k, v in row.items() if k}
                yield clean_row

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
            if r.get('Phone Number'): rider.phone = r.get('Phone Number') # Verified
            if r.get('FB URL'): rider.facebook_url = r.get('FB URL')
            if r.get('IG URL'): rider.instagram_url = r.get('IG URL')
            if r.get('Website URL'): rider.magic_link = r.get('Website URL') # Using Website column for link placeholder
            
            # Tags (Airtable sends list of strings)
            tags = r.get('Tags')
            if tags and isinstance(tags, list):
                rider.tags = ",".join(tags) 
            
            # Scores (Day 1)
            if r.get('Overall Score'): rider.day1_score = float(r.get('Overall Score'))
            if r.get('Biggest Mistake'): rider.biggest_mistake = r.get('Biggest Mistake')
            
            # Dates
            if r.get('Date Blueprint Started'): rider.outreach_date = self._parse_date(r.get('Date Blueprint Started'))
            if r.get('Date Day 1'): rider.day1_date = self._parse_date(r.get('Date Day 1'))
            
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

        # CRM Fields (The "State" we need to persist)
        if r.get('Notes'): rider.notes = r.get('Notes')
        if r.get('Championship'): rider.championship = r.get('Championship')
        if r.get('Follow Up Date'): rider.follow_up_date = self._parse_date(r.get('Follow Up Date'))

    def _load_rider_database(self):
        """Load the main 'Rider Database.csv' for contact info"""
        filename = "Rider Database.csv"
        
        # Debug: Print first row keys to help diagnosis
        debug_printed = False
        
        if 'total' not in self.load_report: self.load_report = {'total': 0, 'loaded': 0, 'skipped': 0, 'reasons': {}}

        for row in self._get_data_iter(filename):
            self.load_report['total'] += 1
            try:
                if not debug_printed:
                    # identifying headers
                    # print(f"DEBUG Headers: {list(row.keys())}") 
                    debug_printed = True

                # --- 1. EMAIL ---
                # Search for any key containing 'email'
                email = None
                for k in row.keys():
                    if 'email' in k:
                        email = row[k]
                        break
                
                # Fallback: ID column if it looks like a no_email key
                if not email:
                    for k in ['id', 'user_id']:
                         val = row.get(k, '').strip()
                         if val.startswith("no_email_"):
                             email = val
                             break

                if email: email = email.strip()
                
                # --- 2. NAME ---
                first_name = row.get("first name") or row.get("first_name") or row.get("firstname")
                if not first_name:
                    # Split 'name' or 'full name' or 'rider'
                    full = row.get("name") or row.get("full name") or row.get("fullname") or row.get("rider") or row.get("competitor") or row.get("driver") or row.get("rider name")
                    if full:
                        parts = full.strip().split(' ')
                        first_name = parts[0]
                        if len(parts) > 1: row["last name"] = " ".join(parts[1:]) # Inject for next step

                last_name = row.get("last name") or row.get("last_name") or row.get("lastname") or row.get("surname")
                
                if first_name: first_name = first_name.strip()
                if last_name: last_name = last_name.strip()
                
                # --- 3. IDENTITY RESCUE (If no email) ---
                # CHANGE: Use clean Name as ID if Email is missing.
                
                if not email:
                    if first_name:
                         # Construct ID from Name (Clean Slug)
                         # e.g. "Aaron Smith" -> "aaron_smith"
                         slug = f"{first_name or ''} {last_name or ''}".lower().strip().replace(' ', '_')
                         
                         # Remove common noise chars
                         slug = "".join([c for c in slug if c.isalnum() or c == '_'])
                         
                         if not slug: slug = "unknown_rider"
                         email = slug # No "no_email_" prefix
                
                if not email:
                    # LOG SKIP
                    reason = "Missing Identity (Col 1 Empty & No Name found)"
                    self.load_report['skipped'] += 1
                    self.load_report['reasons'][reason] = self.load_report['reasons'].get(reason, 0) + 1
                    continue # ID is mandatory
                    
                rider = self._get_or_create_rider(email, first_name or "", last_name or "")
                self.load_report['loaded'] += 1
                
                # DATE FIX
                date_joined_str = row.get("date_joined")
                if date_joined_str and not rider.outreach_date:
                    rider.outreach_date = self._parse_date(date_joined_str)

                # MIGRATION FIX
                if rider.current_stage == FunnelStage.MESSAGED and not rider.outreach_date:
                     rider.current_stage = FunnelStage.CONTACT
                
                # --- 4. SOCIALS (Broad matching) ---
                # Facebook
                fb_url = None
                for k in row.keys():
                    if 'facebook' in k or k == 'fb':
                        fb_url = row[k]
                        break
                if fb_url: rider.facebook_url = fb_url.strip()
                
                # Phone
                phone = None
                for k in row.keys():
                    if 'phone' in k:
                        phone = row[k]
                        break
                if phone: rider.phone = phone.strip()

                # Instagram
                # Look for 'instagram', 'ig', 'user name', 'username'
                ig_val = None
                for k in row.keys():
                   if 'instagram' in k or k == 'ig' or 'username' in k:
                       ig_val = row[k]
                       # Prioritize explicit instagram columns
                       if 'instagram' in k: break 
                
                if ig_val:
                     ig_val = ig_val.strip()
                     if "instagram.com" in ig_val:
                         rider.instagram_url = ig_val
                     elif not ig_val.startswith("http") and "facebook" not in ig_val: # Avoid confused mapping
                         rider.instagram_url = f"https://www.instagram.com/{ig_val}/"
                     else:
                         rider.instagram_url = ig_val 
                
                # --- 5. CRM FIELDS (Notes, Status, Revenue) ---
                
                # Championship
                champ = row.get('championship') or row.get('series') or row.get('class')
                if champ: rider.championship = champ.strip()

                # Notes
                notes = row.get('notes') or row.get('note') or row.get('comments')
                if notes: rider.notes = notes.strip()
                
                # Revenue / Sale Value
                rev = row.get('revenue') or row.get('sale value') or row.get('sale_value') or row.get('amount')
                if rev:
                    try:
                        # strip currency
                        rev_clean = str(rev).replace('£','').replace('$','').replace(',','').strip()
                        rider.sale_value = float(rev_clean)
                    except: pass

                # Status / Stage Mapping
                # Allow explicit overwrite of stage from CSV
                status_raw = row.get('status') or row.get('stage')
                if status_raw:
                    # Try to map string to Enum
                    # We iterate enums to find match
                    found_stage = None
                    s_clean = status_raw.strip().lower()
                    
                    for stage in FunnelStage:
                        if stage.value.lower() == s_clean:
                            found_stage = stage
                            break
                        # Alias checks
                        if s_clean == 'client' or s_clean == 'won': found_stage = FunnelStage.CLIENT
                        if s_clean == 'lost' or s_clean == 'not a fit': found_stage = FunnelStage.NOT_A_FIT
                        if s_clean == 'messaged' or s_clean == 'outreach': found_stage = FunnelStage.MESSAGED
                    
                    if found_stage:
                        rider.current_stage = found_stage
                
                # Boolean Flags (Client / Not a fit) - Overrides status if present
                is_client = row.get('client') or row.get('is_client')
                if is_client and str(is_client).lower() in ['yes', 'true', '1', 'y']:
                    rider.current_stage = FunnelStage.CLIENT
                    if not rider.sale_closed_date: rider.sale_closed_date = datetime.now() # Approximate
                
                not_fit = row.get('not a fit') or row.get('not_fit') or row.get('dq')
                if not_fit and str(not_fit).lower() in ['yes', 'true', '1', 'y']:
                    rider.current_stage = FunnelStage.NOT_A_FIT
                    rider.is_disqualified = True

                # Follow Up Date
                fu_str = row.get('follow up') or row.get('follow_up')
                if fu_str:
                    try:
                        rider.follow_up_date = self._parse_date(fu_str)
                    except: pass

                # Explicitly update name
                if first_name: rider.first_name = first_name
                if last_name: rider.last_name = last_name

            except Exception as e:
                pass # Skip bad rows silently


    def sync_database_to_airtable(self) -> int:
        """
        Manually sync ALL loaded riders to Airtable.
        Returns the number of riders successfully synced.
        """
        if not self.airtable:
            print("No Airtable connection.")
            return 0
            
        count = 0
        total = len(self.riders)
        print(f"Starting bulk sync for {total} riders...")
        
        for email, rider in self.riders.items():
            try:
                # Basic Mapping
                data = {
                    "Email": rider.email,
                    "First Name": rider.first_name,
                    "Last Name": rider.last_name,
                    "FB URL": rider.facebook_url,
                    "IG URL": rider.instagram_url,
                    "Stage": rider.current_stage.value.title() if rider.current_stage else "Contact",
                    "Phone Number": rider.phone,
                    "Championship": rider.championship,
                    "Date Blueprint Started": rider.outreach_date.strftime('%Y-%m-%d') if rider.outreach_date else None,
                }
                
                # clean empty
                clean_data = {k: v for k, v in data.items() if v}
                
                success = self.airtable.upsert_rider(clean_data)
                if success:
                    count += 1
            except Exception as e:
                print(f"Failed to sync {email}: {e}")
                
        return count

    def add_new_rider_to_db(self, email: str, first_name: str, last_name: str, fb_url: str, ig_url: str = "", championship: str = "", **kwargs) -> bool:
        """Manually add a new rider to Rider Database.csv"""
        filename = "Rider Database.csv"
        filepath = os.path.join(self.data_dir, filename)
        
        # Headers used in _load_rider_database mapping
        # We'll use standard ScoreApp/Export headers to match
        fieldnames = ['Full Name', 'Email Address', 'First Name', 'Last Name', 'Facebook URL', 'Instagram URL', 'Championship', 'Phone Number', 'Status', 'Date Joined', 'Notes']
        
        full_name = f"{first_name} {last_name}".strip()
        
        try:
            file_exists = os.path.exists(filepath)
            
            with open(filepath, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                
                if not file_exists:
                    writer.writeheader()
                    
                writer.writerow({
                    'Full Name': full_name,
                    'Email Address': email,
                    'First Name': first_name,
                    'Last Name': last_name,
                    'Facebook URL': fb_url,
                    'Instagram URL': ig_url,
                    'Championship': championship,
                    'Phone Number': kwargs.get('phone', ''),
                    'Status': 'Contact',
                    'Date Joined': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'Notes': kwargs.get('notes', 'Added via App')
                })
            
            # --- AIRTABLE SYNC (CLOUD NATIVE) ---
            if self.airtable:
                try:
                    at_data = {
                        "Email": email,
                        "First Name": first_name,
                        "Last Name": last_name,
                        "Facebook URL": fb_url,
                        "Instagram URL": ig_url,
                        "Championship": championship,
                        "Phone Number": kwargs.get('phone', ''),
                        "Notes": kwargs.get('notes', ''),
                    }
                    if 'follow_up_date' in kwargs and kwargs['follow_up_date']:
                        at_data['Follow Up Date'] = kwargs['follow_up_date'].strftime('%Y-%m-%d')
                        
                    self.airtable.upsert_rider(at_data)
                except Exception: pass
                
            # CRITICAL: Also update overrides if they exist (GSheet Mode)
            # because reload_data() prefers overrides over the file we just wrote.
            if self.overrides and filename in self.overrides:
                df = self.overrides[filename]
                if isinstance(df, pd.DataFrame):
                    new_row = {
                        'Full Name': full_name,
                        'Email Address': email,
                        'First Name': first_name,
                        'Last Name': last_name,
                        'Facebook URL': fb_url,
                        'Instagram URL': ig_url,
                        'Championship': championship,
                        'Phone Number': '',
                        'Status': 'Contact',
                        'Date Joined': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'Notes': 'Added via App'
                    }
                    # Append strictly matching existing columns to avoid errors
                    # Only add keys that exist in current DF to be safe
                    safe_row = {k: v for k, v in new_row.items() if k in df.columns}
                    
                    # Create 1-row DF
                    row_df = pd.DataFrame([safe_row])
                    # Concat
                    self.overrides[filename] = pd.concat([df, row_df], ignore_index=True)

                    # --- GSHEET WRITE-BACK ---
                    try:
                        import streamlit as st
                        import gsheets_loader
                        
                        # Only proceed if we have the URL and the loader module
                        if "sheets" in st.secrets and "rider_db" in st.secrets["sheets"]:
                            sheet_url = st.secrets["sheets"]["rider_db"]
                            
                            # Construct row values based on the DataFrame keys (Source of Truth for Column Order)
                            # This ensures we put the email in the 'email' column, not 'id' etc.
                            sheet_row = []
                            for col in df.columns:
                                val = ""
                                c = str(col).lower().strip()
                                
                                if c in ['full name', 'full_name', 'name']: val = full_name
                                elif c in ['email', 'email address', 'email_address']: val = email
                                elif c in ['first name', 'first_name']: val = first_name
                                elif c in ['last name', 'last_name']: val = last_name
                                elif c in ['facebook url', 'facebook_url', 'fb']: val = fb_url
                                elif c in ['instagram url', 'instagram_url', 'instagram', 'ig']: val = ig_url
                                elif c in ['championship']: val = championship
                                elif c in ['date_joined', 'date joined']: val = datetime.now().strftime('%Y-%m-%d')
                                elif c in ['status', 'stage']: val = 'Contact'
                                elif c in ['notes', 'comments']: val = 'Added via App'
                                elif c in ['id']: 
                                    # Generate a temp ID or leave blank? 
                                    # Let's use a random ID to minimize collision if the sheet doesn't auto-gen
                                    val = str(random.randint(2000000, 9999999)) 
                                
                                sheet_row.append(val)
                                
                            # Append to Sheet
                            success = gsheets_loader.append_row_to_sheet(sheet_url, sheet_row)
                            if success:
                                print(f"Successfully appended {email} to Google Sheet")
                            else:
                                print("Failed to append to Google Sheet")
                                
                    except ImportError:
                        pass # Not running in Streamlit or gsheets_loader missing
                    except Exception as e:
                        print(f"GSheet Sync Error: {e}")
                
            # Update In-Memory
            rider = self._get_or_create_rider(email, first_name, last_name)
            if fb_url:
                rider.facebook_url = fb_url
            if ig_url:
                rider.instagram_url = ig_url
            if championship:
                rider.championship = championship
                
            return True
        except Exception as e:
            print(f"Error adding rider: {e}")
            return False

            # --- AIRTABLE SYNC ---
            if self.airtable:
                 try:
                     self.airtable.upsert_rider({
                         "Email": email,
                         "First Name": first_name,
                         "Last Name": last_name,
                         "FB URL": fb_url,
                         "IG URL": ig_url,
                         "Stage": "Contact",
                         "Date Blueprint Started": datetime.now().strftime('%Y-%m-%d')
                     })
                     print(f"Synced {email} to Airtable")
                 except Exception as e:
                     print(f"Airtable Sync Error: {e}")

            return True

        
    def _scan_for_social_and_reviews(self):
        """Scan all CSVs in dir for Social Media columns and Review dates"""
        if not os.path.exists(self.data_dir):
            return

        for filename in os.listdir(self.data_dir):
            if not filename.endswith(".csv"):
                continue
                
            filepath = os.path.join(self.data_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    if not reader.fieldnames:
                        continue
                        
                    # Normalize headers
                    headers = [h.lower() for h in reader.fieldnames]
                    
                    has_email = 'email' in headers
                    if not has_email:
                        continue
                        
                    # 1. Check for specific Review Types by unique columns
                    # Race Weekend Review (export 15) has "what circuit did you race at this weekend?"
                    is_race_review = any("what circuit did you race at" in h for h in headers) or 'race weekend' in filename.lower()
                    
                    # End of Season Review (export 16) has "what championship did you race in?" (and explicitly mentions season)
                    is_season_review = any("what championship did you race in" in h for h in headers) or 'end of season' in filename.lower()
                    
                    # 2. Check for Social Links (Generic)
                    has_fb = any('facebook' in h for h in headers)
                    has_ig = any('instagram' in h for h in headers)
                    has_li = any('linked' in h for h in headers)
                    
                    if not (has_fb or has_ig or has_li or is_race_review or is_season_review):
                        continue
                        
                    # Process rows
                    for row in reader:
                        # Handle case-insensitive 'email' lookup
                        email = None
                        for k, v in row.items():
                            if k.lower() == 'email':
                                email = v
                                break
                        
                        if not email or '@' not in email:
                            continue
                            
                        rider = self._get_or_create_rider(email)
                        
                        # Extract Socials
                        for col in row.keys():
                            c_low = col.lower()
                            val = row[col].strip()
                            if not val:
                                continue
                                
                            if 'facebook' in c_low and 'url' in c_low:
                                rider.facebook_url = val
                            elif 'instagram' in c_low and 'url' in c_low:
                                rider.instagram_url = val
                            elif 'linked' in c_low and 'url' in c_low:
                                rider.linkedin_url = val
                        
                        # Extract Name if missing
                        if not rider.first_name and 'first_name' in headers:
                             rider.first_name = row.get('first_name', '')
                        if not rider.last_name and 'last_name' in headers:
                             rider.last_name = row.get('last_name', '')

                        # Extract Dates (ScoreApp standard: 'scorecard_finished_at' or 'submit date (utc)')
                        date_str = row.get('scorecard_finished_at') or row.get('submit_date_utc') or row.get('Sumit Date (UTC)') or row.get('Submit Date (UTC)')
                        
                        submit_date = self._parse_date(date_str) if date_str else None
                        
                        if is_race_review and submit_date:
                            if not rider.race_weekend_review_date or submit_date > rider.race_weekend_review_date:
                                rider.race_weekend_review_date = submit_date
                                rider.race_weekend_review_status = "completed"
                                
                                # --- AIRTABLE SYNC ---
                                if self.airtable:
                                    try:
                                        self.airtable.upsert_rider({
                                            "Email": email,
                                            "Date Race Review": submit_date.strftime('%Y-%m-%d')
                                        })
                                    except Exception: pass
                            
                        if is_season_review and submit_date:
                            if not rider.end_of_season_review_date or submit_date > rider.end_of_season_review_date:
                                rider.end_of_season_review_date = submit_date

            except Exception:
                pass # Skip bad files

    def save_revenue(self, email: str, amount: float):
        """Save revenue entry to CSV"""
        filepath = os.path.join(self.data_dir, 'revenue_log.csv')
        
        with open(filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(['email', 'amount', 'timestamp'])
            writer.writerow([email, amount, datetime.now().isoformat()])
            
        # Update in-memory
        rider = self.riders.get(email.lower())
        if rider:
            rider.sale_value = amount

    def _load_revenue_log(self):
        """Load revenue_log.csv"""
        filepath = os.path.join(self.data_dir, 'revenue_log.csv')
        if not os.path.exists(filepath):
            return
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get('email', '').strip().lower()
                    try:
                        amount = float(row.get('amount', 0))
                    except ValueError:
                        continue
                        
                    if email and amount > 0:
                        rider = self._get_or_create_rider(email)
                        rider.sale_value = amount
                        # Assume sale closed if revenue present
                        if rider.current_stage != FunnelStage.SALE_CLOSED:
                             rider.current_stage = FunnelStage.SALE_CLOSED
        except Exception:
            pass

    def save_manual_update(self, email: str, stage: FunnelStage):
        """Save a manual stage update to CSV"""
        filepath = os.path.join(self.data_dir, 'manual_updates.csv')
        
        # Write mode 'a' (append)
        with open(filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Init file with header if empty
            if f.tell() == 0:
                writer.writerow(['email', 'stage', 'timestamp'])
                
            writer.writerow([email, stage, datetime.now().isoformat()])
            
        # Update in-memory
        if email in self.riders:
            matched_stage = None
            for s in FunnelStage:
                if s.value == stage:
                    matched_stage = s
                    break
            
            if matched_stage:
                self.riders[email].current_stage = matched_stage
                # Update date in memory for immediate UI feedback
                if matched_stage == FunnelStage.MESSAGED:
                    self.riders[email].outreach_date = datetime.now()

            
    def save_rider_details(self, email: str, **kwargs):
        """
        Save custom CRM fields (notes, follow_up, championship, etc.) to rider_details.csv
        and update the in-memory Rider object.
        """
        filepath = os.path.join(self.data_dir, 'rider_details.csv')
        
        # 1. Update in-memory Rider immediately
        rider = self._get_or_create_rider(email)
        for k, v in kwargs.items():
            if hasattr(rider, k):
                setattr(rider, k, v)
        
        # 2. Persist to CSV (Append Only Log for now, could be optimized to database later)
        # Structure: email, timestamp, field, value
        with open(filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(['email', 'timestamp', 'field', 'value'])
            
            ts = datetime.now().isoformat()
            for k, v in kwargs.items():
                val_str = v.isoformat() if isinstance(v, datetime) else str(v)
                writer.writerow([email, ts, k, val_str])

        # --- GSHEET SYNC (EDITS) ---
        try:
            import streamlit as st
            import gsheets_loader
            
            if "sheets" in st.secrets and "rider_db" in st.secrets["sheets"]:
                sheet_url = st.secrets["sheets"]["rider_db"]
                
                # Find Row
                row_idx = gsheets_loader.find_row_by_email(sheet_url, email)
                
                if row_idx:
                    for k, v in kwargs.items():
                        # Prepare value
                        val_str = v.strftime('%Y-%m-%d') if hasattr(v, 'strftime') else str(v)
                        
                        target_header = None
                        if k == 'notes': target_header = 'notes' # Lowercase match
                        if k == 'championship': target_header = 'Championship'
                        if k == 'follow_up_date': target_header = 'Follow Up'
                        if k == 'phone': target_header = 'Phone Number'
                        # Add more mappings as needed

                        if target_header:
                            gsheets_loader.update_cell_by_header(sheet_url, row_idx, target_header, val_str)

        except Exception as e:
            print(f"GSheet Edit Sync Error: {e}")

        # --- AIRTABLE SYNC (Source of Truth) ---
        if self.airtable:
            try:
                # Prepare Payload
                data = {"Email": email}
                
                # Map Kwargs to Airtable Columns
                if 'notes' in kwargs: data['Notes'] = kwargs['notes']
                if 'championship' in kwargs: data['Championship'] = kwargs['championship']
                if 'follow_up_date' in kwargs: 
                    d = kwargs['follow_up_date']
                    data['Follow Up Date'] = d.strftime('%Y-%m-%d') if d else None
                if 'phone' in kwargs: data['Phone Number'] = kwargs['phone']
                if 'sale_value' in kwargs: data['Revenue'] = kwargs['sale_value']
                
                # Upsert
                self.airtable.upsert_rider(data)

            except Exception as e:
                print(f"Airtable Edit Sync Error: {e}")

    def sync_missing_riders_to_db(self):
        """
        Identify riders currently in memory (e.g. from FB, manual adds) that are NOT in Rider Database.csv
        and append them to the CSV.
        """
        db_file = os.path.join(self.data_dir, "Rider Database.csv")
        
        # 1. Load existing emails from CSV to avoid duplicates
        existing_emails = set()
        if os.path.exists(db_file):
            with open(db_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'email' in row and row['email']:
                        existing_emails.add(row['email'].strip().lower())
        
        # 2. Find Riders to Add
        riders_to_add = []
        for r in self.riders.values():
            if r.email.lower() not in existing_emails:
                riders_to_add.append(r)
                
        if not riders_to_add:
            return 0
            
        # 3. Append to CSV
        # We need to respect existing headers if possible.
        # If file doesn't exist, we create it.
        
        file_exists = os.path.exists(db_file)
        mode = 'a'
        
        # Standard Headers we want to ensure
        base_headers = ['first_name', 'last_name', 'email', 'date_joined', 'phone', 'notes', 'tags']
        
        try:
            with open(db_file, mode, newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # If creating or appending to empty file
                if not file_exists or f.tell() == 0:
                    writer.writerow(base_headers)
                    
                for r in riders_to_add:
                    # Map Rider to Row
                    # We only fill basic details to handle the import
                    row_data = []
                    
                    # We need to know the columns of the CSV to write correctly? 
                    # Simpler approach: Just read headers first if exists, else use base.
                    # WRONG: Append must match existing column order.
                    pass 
            
            # Re-opening with DictWriter is safer if headers exist
            fieldnames = base_headers
            if file_exists:
                with open(db_file, 'r', encoding='utf-8') as fr:
                    reader = csv.DictReader(fr)
                    if reader.fieldnames:
                        fieldnames = reader.fieldnames
            
            with open(db_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                if not file_exists:
                    writer.writeheader()
                    
                for r in riders_to_add:
                    writer.writerow({
                        'first_name': r.first_name,
                        'last_name': r.last_name,
                        'email': r.email,
                        'date_joined': r.outreach_date.strftime('%Y-%m-%d') if r.outreach_date else '',
                        'phone': r.phone,
                        'notes': r.notes,
                        'tags': 'imported_contact'
                    })
                    
            return len(riders_to_add)
            
        except Exception as e:
            print(f"Sync Error: {e}")
            return 0

    def _load_rider_details(self):
        """Load rider_details.csv and apply to Riders"""
        filepath = os.path.join(self.data_dir, 'rider_details.csv')
        if not os.path.exists(filepath):
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get('email', '').strip().lower()
                    field_name = row.get('field')
                    value_str = row.get('value')
                    
                    if not email or not field_name: continue
                    
                    rider = self._get_or_create_rider(email)
                    
                    # Type Conversion
                    if field_name == 'follow_up_date':
                        rider.follow_up_date = self._parse_date(value_str)
                    elif field_name == 'is_disqualified':
                        rider.is_disqualified = (value_str == 'True')
                    elif field_name == 'sale_value':
                        try: rider.sale_value = float(value_str)
                        except: pass
                    elif hasattr(rider, field_name):
                        # Generic string fields: notes, championship, disqualification_reason
                        setattr(rider, field_name, value_str)
                        
        except Exception:
            pass # resilient loading

    def _load_manual_updates(self):
        """Load manual_updates.csv"""
        filepath = os.path.join(self.data_dir, 'manual_updates.csv')
        
        if not os.path.exists(filepath):
            return
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get('email', '').strip().lower()
                    stage_val = row.get('stage', '')
                    timestamp_str = row.get('timestamp', '')
                    
                    if not email or not stage_val:
                        continue
                        
                    # Find matching enum
                    matched_stage = None
                    for stage in FunnelStage:
                        if stage.value == stage_val:
                            matched_stage = stage
                            break
                    
                    if matched_stage:
                         rider = self._get_or_create_rider(email)
                         rider.current_stage = matched_stage
                         
                         # DATE FIX: If manually moving to Messaged, use timestamp as outreach_date
                         # Always overwrite to ensure we have the actual interaction time, not just join date
                         if matched_stage == FunnelStage.MESSAGED and timestamp_str:
                             ts = self._parse_date(timestamp_str)
                             if ts:
                                 rider.outreach_date = ts

        except Exception:
            pass # Ignore corrupt manual file

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats"""
        if not date_str:
            return None

        formats = [
            '%d/%m/%Y %H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%m/%d/%Y %H:%M:%S',
            '%m/%d/%Y',
            '%Y-%m-%dT%H:%M:%S.%fZ', # ISO
            '%Y-%m-%dT%H:%M:%SZ',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    def _load_xperiencify_csv(self):
        """Load Xperiencify.csv (Manual Export)"""
        filename = 'Xperiencify.csv'
        
        for row in self._get_data_iter(filename):
            email = row.get('email', '').strip()
            if not email: continue
            
            # Create Rider
            rider = self._get_or_create_rider(
                email,
                row.get('first_name', ''),
                row.get('last_name', '')
            )
            
            # Map Fields
            if row.get('phone'): rider.phone = row.get('phone')
            if row.get('magic_link'): rider.magic_link = row.get('magic_link')
            
            # Dates
            if row.get('date_joined'):
                joined = self._parse_date(row.get('date_joined'))
                if joined:
                    if not rider.registered_date: rider.registered_date = joined
                    if not rider.outreach_date: rider.outreach_date = joined # Fallback
            
            # Tags & Status
            tags_str = row.get('tags', '')
            if tags_str:
                # Merge tags (simple csv append of unique items if needed, or just replace?)
                # Airtable tags are list.
                pass
                
            # Xperiencify Tags -> Stage Mapping
            t_lower = tags_str.lower()
            new_stage = None
            
            if "day 3 completed" in t_lower: 
                # Strategy Call likely next, but they are at least here
                if rider.current_stage.value != "Strategy Call Booked": # Don't regress
                     pass # Maybe "Day 3"? We don't have a specific Day 3 enum, assume Day 2 Complete or similar
            elif "day 2 completed" in t_lower:
                if rider.current_stage not in [FunnelStage.STRATEGY_CALL_BOOKED, FunnelStage.CLIENT]:
                    new_stage = FunnelStage.DAY2_COMPLETE
            elif "day 1 completed" in t_lower:
                 if rider.current_stage not in [FunnelStage.DAY2_COMPLETE, FunnelStage.STRATEGY_CALL_BOOKED, FunnelStage.CLIENT]:
                    new_stage = FunnelStage.DAY1_COMPLETE
            elif "mission accepted" in t_lower or "blueprint started" in t_lower:
                 if rider.current_stage == FunnelStage.OUTREACH or rider.current_stage == FunnelStage.CONTACT:
                    new_stage = FunnelStage.BLUEPRINT_STARTED
            
            if new_stage:
                rider.current_stage = new_stage

            # --- AIRTABLE SYNC ---
            if self.airtable:
                try:
                    # Sync relevant fields
                    data = {
                        "Email": email,
                        "First Name": row.get('first_name', ''),
                        "Last Name": row.get('last_name', ''),
                        "Phone Number": row.get('phone', ''),
                        "Tags": tags_str.split(',') if tags_str else [], # list for multiselect
                        # "Magic Link": row.get('magic_link', ''),
                        "Date Blueprint Started": row.get('date_joined', '')
                    }
                    
                    if new_stage:
                        data["Stage"] = new_stage.value
                        
                    self.airtable.upsert_rider(data)
                except Exception: pass

    def _load_facebook_history(self):
        """Load 'Facebook Messenger History - Sheet1 (1).csv' and add contacts"""
        filename = "Facebook Messenger History - Sheet1 (1).csv"
        filepath = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(filepath):
            return
            
        try:
            # We need to handle the header structure (Row 2 is header)
            # Using pandas for robust parsing of this specific file
            df = pd.read_csv(filepath, header=1)
            
            # Columns of interest: 'title', 'messages__timestamp_ms', 'thread_path'
            if 'title' not in df.columns:
                return
                
            # Group by conversation (title)
            # Filter out 'Craig Muirhead' from titles if he appears there (usually title is the other person or group)
            conversations = df.groupby('title')
            
            for title, group in conversations:
                name = str(title).strip()
                if not name or name.lower() == 'craig muirhead' or name.lower() == 'nan':
                    continue
                    
                # Create Rider
                # We don't have email, so generate slug ID
                # Try to clean name
                clean_name = "".join([c for c in name if c.isalnum() or c == ' ']).strip()
                slug = clean_name.lower().replace(' ', '_')
                
                # Check if this name already matches an existing rider by name?
                # This prevents duplicates if we have them in Rider Database with email
                # but here without.
                
                existing_email = None
                for r in self.riders.values():
                    if r.full_name.lower() == clean_name.lower():
                        existing_email = r.email
                        break
                        
                if existing_email:
                    rider = self.riders[existing_email]
                else:
                    # New Rider
                    fake_email = f"no_email_{slug}"
                    # Split name
                    parts = clean_name.split(' ')
                    fname = parts[0]
                    lname = " ".join(parts[1:]) if len(parts) > 1 else ""
                    
                    rider = self._get_or_create_rider(fake_email, fname, lname)
                    rider.outreach_channel = OutreachChannel.FACEBOOK_DM
                    
                # --- KEY FIX: Force Stage to MESSAGED if they are in this history file ---
                # This ensures they show up as "Messaged"
                # Only upgrade if they are currently lower (e.g. Contact or Outreach)
                if rider.current_stage in [FunnelStage.CONTACT, FunnelStage.OUTREACH]:
                     rider.current_stage = FunnelStage.MESSAGED

                # Update Outreach Date (Earliest message)
                try:
                    timestamps = pd.to_datetime(group['messages__timestamp_ms'], unit='ms', errors='coerce')
                    first_msg = timestamps.min()
                    
                    if not pd.isna(first_msg):
                        # If no outreach date or this is earlier (and valid year), update
                        # Convert pandas timestamp to python datetime
                        first_msg_dt = first_msg.to_pydatetime()
                        
                        if not rider.outreach_date or first_msg_dt < rider.outreach_date:
                            # Sanity check year (some exports have bad dates?)
                            if first_msg_dt.year > 2000:
                                rider.outreach_date = first_msg_dt
                                
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"Error loading FB history: {e}")

    def _get_or_create_rider(self, email: str, first_name: str = '', last_name: str = '') -> Rider:

        """Get existing rider or create new one"""
        email_key = email.lower().strip()

        if email_key not in self.riders:
            self.riders[email_key] = Rider(
                email=email_key,
                first_name=first_name.strip() if first_name else '',
                last_name=last_name.strip() if last_name else ''
            )
        else:
            # Update name if we have better info
            rider = self.riders[email_key]
            if first_name and not rider.first_name:
                rider.first_name = first_name.strip()
            if last_name and not rider.last_name:
                rider.last_name = last_name.strip()

        return self.riders[email_key]

    def _load_strategy_call_applications(self):
        """Load Strategy Call Application.csv"""
        filename = 'Strategy Call Application.csv'

        for row in self._get_data_iter(filename):
            email = row.get('email', '').strip()
            if not email:
                continue

            rider = self._get_or_create_rider(
                email,
                row.get('first_name', ''),
                row.get('last_name', '')
            )

            # Update stage to strategy call booked
            rider.current_stage = FunnelStage.STRATEGY_CALL_BOOKED
            
            # Robust Date Parsing
            date_val = (row.get('submit_date_utc', '') or 
                       row.get('stage_date_utc', '') or 
                       row.get('date', '') or 
                       row.get('timestamp', '') or
                       row.get('created at', '') or
                       row.get('submit date', ''))
                       
            rider.strategy_call_booked_date = self._parse_date(date_val)

            # Additional data
            rider.phone = row.get('phone', '')
            rider.country = row.get('country', '')
            rider.rider_type = row.get('rider_type', '')
            rider.championship = row.get('championship_racing_in', '')

            # --- AIRTABLE SYNC ---
            if self.airtable:
                try:
                    self.airtable.upsert_rider({
                        "Email": email,
                        "First Name": row.get('first_name', ''),
                        "Last Name": row.get('last_name', ''),
                        "Stage": "Strategy Call",
                        "Date Strategy Call": rider.strategy_call_booked_date.strftime('%Y-%m-%d') if rider.strategy_call_booked_date else None
                    })
                except Exception: pass

    def _load_blueprint_registrations(self):
        """Load Podium Contenders Blueprint Registered.csv"""
        filename = 'Podium Contenders Blueprint Registered.csv'

        for row in self._get_data_iter(filename):
            email = row.get('email', '').strip()
            if not email:
                continue

            rider = self._get_or_create_rider(
                email,
                row.get('first_name', ''),
                row.get('last_name', '')
            )

            # Only update if not already further in funnel
            if rider.current_stage == FunnelStage.OUTREACH:
                rider.current_stage = FunnelStage.REGISTERED

            # Robust Date Parsing
            date_val = (row.get('submit_date_utc', '') or 
                       row.get('stage_date_utc', '') or 
                       row.get('date', '') or 
                       row.get('timestamp', '') or
                       row.get('created at', '') or
                       row.get('submit date', ''))
                       
            rider.registered_date = self._parse_date(date_val)

            # Additional data
            if not rider.phone:
                rider.phone = row.get('phone', '')
            if not rider.country:
                rider.country = row.get('country', '')
            if not rider.rider_type:
                rider.rider_type = row.get('rider_type', '')

    def _load_day1_assessments(self):
        """Load 7 Biggest Mistakes Assessment.csv"""
        filename = '7 Biggest Mistakes Assessment.csv'

        for row in self._get_data_iter(filename):
            email = row.get('email', '').strip()
            if not email:
                continue

            # Check if completed
            completed = row.get('completed', '').lower() == 'yes'
            if not completed:
                continue

            rider = self._get_or_create_rider(
                email,
                row.get('first_name', ''),
                row.get('last_name', '')
            )

            # Update stage if not already further
            if rider.current_stage in [FunnelStage.OUTREACH, FunnelStage.REGISTERED]:
                rider.current_stage = FunnelStage.DAY1_COMPLETE

            # Robust Date Parsing
            date_val = (row.get('scorecard_finished_at', '') or 
                       row.get('submit_date_utc', '') or 
                       row.get('date', '') or 
                       row.get('timestamp', '') or
                       row.get('created at', '') or
                       row.get('submit date', ''))
                       
            rider.day1_complete_date = self._parse_date(date_val)

            # Extract overall score
            try:
                score_str = row.get('Overall Score - Actual', '0')
                rider.day1_score = float(score_str) if score_str else None
            except ValueError:
                pass

    def _load_day2_assessments(self):
        """Load Day 2 Self Assessment.csv"""
        filename = 'Day 2 Self Assessment.csv'

        for row in self._get_data_iter(filename):
            email = row.get('email', '').strip()
            if not email:
                continue

            rider = self._get_or_create_rider(
                email,
                row.get('first_name', ''),
                row.get('last_name', '')
            )

            # Update stage if not already further
            if rider.current_stage in [FunnelStage.OUTREACH, FunnelStage.REGISTERED, FunnelStage.DAY1_COMPLETE]:
                rider.current_stage = FunnelStage.DAY2_COMPLETE

            # Robust Date Parsing
            date_val = (row.get('submit_date_utc', '') or 
                       row.get('stage_date_utc', '') or 
                       row.get('date', '') or 
                       row.get('timestamp', '') or
                       row.get('created at', '') or
                       row.get('submit date', ''))
                       
            rider.day2_complete_date = self._parse_date(date_val)

            # Extract pillar scores
            rider.day2_scores = {}
            pillar_keys = [
                ('Pillar 1', 'mindset'),
                ('Pillar 2', 'preparation'),
                ('Pillar 3', 'flow'),
                ('Pillar 4', 'feedback'),
                ('Pillar 5', 'sponsorship'),
            ]

            for csv_key, score_key in pillar_keys:
                for col in row.keys():
                    if csv_key.lower() in col.lower() and 'rate' in col.lower():
                        try:
                            rider.day2_scores[score_key] = float(row[col])
                        except (ValueError, TypeError):
                            pass
                        except (ValueError, TypeError):
                            pass
                        break

            # --- AIRTABLE SYNC ---
            if self.airtable:
                try:
                    self.airtable.upsert_rider({
                        "Email": email,
                        "First Name": row.get('first_name', ''),
                        "Last Name": row.get('last_name', ''),
                        "Stage": "Day 2",
                        "Date Day 2": rider.day2_complete_date.strftime('%Y-%m-%d') if rider.day2_complete_date else None
                    })
                except Exception: pass

    def _load_sleep_test(self):
        """Load Sleep Test.csv"""
        filename = 'Sleep Test.csv'
        
        for row in self._get_data_iter(filename):
            email = row.get('email', '').strip()
            if not email:
                continue

            rider = self._get_or_create_rider(
                email,
                row.get('first_name', ''),
                row.get('last_name', '')
            )
            
            rider.sleep_test_date = self._parse_date(
                row.get('submit_date_utc', '') or row.get('stage_date_utc', '')
            )
            
            try:
                score = row.get('Overall Score - Actual', '') or row.get('Score', '')
                if score:
                    rider.sleep_score = float(score)
            except ValueError:
                pass
            
            # --- UPDATE STAGE ---
            if rider.current_stage in [FunnelStage.CONTACT, FunnelStage.OUTREACH]:
                rider.current_stage = FunnelStage.SLEEP_TEST_COMPLETED
            
            # --- AIRTABLE SYNC ---
            if self.airtable:
                try:
                    self.airtable.upsert_rider({
                        "Email": email,
                        "First Name": row.get('first_name', ''),
                        "Last Name": row.get('last_name', ''),
                        "Date Sleep Test": rider.sleep_test_date.strftime('%Y-%m-%d') if rider.sleep_test_date else None,
                        # "Sleep Score": rider.sleep_score
                    })
                except Exception: pass

    def _load_mindset_quiz(self):
        """Load Mindset Quiz.csv"""
        filename = 'Mindset Quiz.csv'
        
        for row in self._get_data_iter(filename):
            email = row.get('email', '').strip()
            if not email:
                continue

            rider = self._get_or_create_rider(
                email,
                row.get('first_name', ''),
                row.get('last_name', '')
            )
            
            rider.mindset_quiz_date = self._parse_date(
                row.get('submit_date_utc', '') or row.get('stage_date_utc', '')
            )
            
            # Result extraction (Type/Score)
            try:
                score = row.get('Overall Score - Actual', '') or row.get('Score', '')
                if score:
                    rider.mindset_score = float(score)
            except ValueError:
                pass
            
            outcome = row.get('Outcome', '') or row.get('Your Mindset', '')
            if outcome:
                rider.mindset_result = outcome.strip()

            # --- UPDATE STAGE ---
            if rider.current_stage in [FunnelStage.CONTACT, FunnelStage.OUTREACH]:
                rider.current_stage = FunnelStage.MINDSET_QUIZ_COMPLETED

            # --- AIRTABLE SYNC ---
            if self.airtable:
                try:
                    self.airtable.upsert_rider({
                        "Email": email,
                        "First Name": row.get('first_name', ''),
                        "Last Name": row.get('last_name', ''),
                        "Date Mindset Quiz": rider.mindset_quiz_date.strftime('%Y-%m-%d') if rider.mindset_quiz_date else None,
                        # "Mindset Score": rider.mindset_score
                        # "Mindset Result": rider.mindset_result # Can add if schema supports it
                    })
                except Exception: pass

    def _load_flow_profile_results(self):
        """Load Flow Profile.csv"""
        filename = 'Flow Profile.csv'

        for row in self._get_data_iter(filename):
            email = row.get('email', '').strip()
            if not email:
                continue

            rider = self._get_or_create_rider(
                email,
                row.get('first name', ''),
                row.get('last name', '')
            )

            # Map fields
            # Submit Date (UTC) -> flow_profile_date
            rider.flow_profile_date = self._parse_date(
                row.get('submit date (utc)', '')
            )

            # Score -> flow_profile_score
            try:
                rider.flow_profile_score = float(row.get('score', '0'))
            except (ValueError, TypeError):
                pass

            # Ending -> flow_profile_url and result
            ending_url = row.get('ending', '')
            rider.flow_profile_url = ending_url
            
            # --- UPDATE STAGE ---
            # If they are just a contact, move them to Flow Profile Completed so they show on dashboard
            if rider.current_stage in [FunnelStage.CONTACT, FunnelStage.OUTREACH]:
                rider.current_stage = FunnelStage.FLOW_PROFILE_COMPLETED
            
            # Derive result from URL if possible, or use a default if not clear
            # The prompt implies the result might be "Go Getter" or "Deep Thinker"
            # Looking at the CSV sample, there isn't a direct "Result" column other than implicit in URL
            # unless we parse it.
            if ending_url:
                if 'go-getter' in ending_url.lower():
                    rider.flow_profile_result = "Go Getter"
                elif 'deepthinker' in ending_url.lower():
                    rider.flow_profile_result = "Deep Thinker"
                else:
                    rider.flow_profile_result = "Completed" # Fallback

            # --- AIRTABLE SYNC ---
            if self.airtable:
                try:
                    self.airtable.upsert_rider({
                        "Email": email,
                        "First Name": row.get('First name', ''),
                        "Last Name": row.get('Last name', ''),
                        "Date Flow Profile": rider.flow_profile_date.strftime('%Y-%m-%d') if rider.flow_profile_date else None,
                        # "Flow Profile Type": rider.flow_profile_result
                    })
                except Exception: pass

    def _load_race_reviews(self):
        """Load export (15).csv (Race Reviews)"""
        filename = 'export (15).csv'
        
        for row in self._get_data_iter(filename):
            email = row.get('email', '').strip()
            if not email: continue
            
            rider = self._get_or_create_rider(
                email,
                row.get('first_name', ''),
                row.get('last_name', '')
            )
            
            # Parse Date
            # Usually: 'scorecard_finished_at' or 'submit date (utc)'
            date_val = row.get('scorecard_finished_at') or row.get('submit_date_utc') or row.get('Submit Date (UTC)')
            submit_date = self._parse_date(date_val)
            
            if submit_date:
                # Update if new
                if not rider.race_weekend_review_date or submit_date > rider.race_weekend_review_date:
                    rider.race_weekend_review_date = submit_date
                    rider.race_weekend_review_status = "completed"
                    
                    # --- AIRTABLE SYNC ---
                    if self.airtable:
                        try:
                            self.airtable.upsert_rider({
                                "Email": email,
                                "Date Race Review": submit_date.strftime('%Y-%m-%d')
                            })
                        except Exception: pass


# =============================================================================
# FUNNEL DASHBOARD
# =============================================================================

class FunnelDashboard:
    """Main dashboard for funnel management"""

    def __init__(self, data_dir: str, overrides: Optional[Dict[str, Any]] = None):
        self.data_dir = data_dir
        self.data_loader = DataLoader(data_dir, overrides=overrides)
        self.calculator = FunnelCalculator()
        self.rescue_manager = RescueMessageManager()
        self.followup_manager = FollowUpMessageManager()
        self.daily_stats = DailyStatsManager(data_dir) # Init Manual Stats
        # Initialize Race Manager after data load
        self.riders: Dict[str, Rider] = {}
        
        # Load data first
        self.reload_data()
        
        # Now init race manager with populated loader
        self.race_manager = RaceResultManager(self.data_loader)

    @property
    def airtable(self):
        return self.data_loader.airtable

    def reload_data(self):
        """Reload all data from CSV files"""
        self.riders = self.data_loader.load_all_data()
        self._calculate_conversion_rates()
        # Reload manual stats
        self.daily_stats = DailyStatsManager(self.data_dir)
        # Re-sync race manager if needed (though it shares reference)
        if hasattr(self, 'race_manager'):
            self.race_manager.riders = self.riders
            
    # Proxy methods for Race Results
    def process_race_results(self, raw_names: List[str], event_name: str) -> List[Dict]:
        return self.race_manager.process_race_results(raw_names, event_name)
        
    def import_crm_csv(self, file_obj) -> Dict[str, int]:
        """Import a generic CRM CSV and map standard columns"""
        stats = {'added': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        try:
            # Read CSV
            df = pd.read_csv(file_obj)
            
            # Normalize Headers
            df.columns = [c.strip().lower() for c in df.columns]
            
            # Map Columns (Try to find standard variations)
            col_map = {}
            possible_emails = ['email', 'email address', 'e-mail', 'contact email']
            possible_first = ['first name', 'first', 'given name', 'forename']
            possible_last = ['last name', 'last', 'surname', 'family name']
            possible_phone = ['phone', 'phone number', 'mobile', 'cell']
            
            for col in df.columns:
                if col in possible_emails and 'email' not in col_map: col_map['email'] = col
                if col in possible_first and 'first' not in col_map: col_map['first'] = col
                if col in possible_last and 'last' not in col_map: col_map['last'] = col
                if col in possible_phone and 'phone' not in col_map: col_map['phone'] = col
            
            if 'email' not in col_map:
                stats['errors'] = 1
                return stats # Cannot proceed without email
                
            # Iterate and Add
            for _, row in df.iterrows():
                email = str(row.get(col_map['email'], '')).strip().lower()
                if not email or '@' not in email:
                    stats['skipped'] += 1
                    continue
                    
                first = str(row.get(col_map.get('first'), '')).strip() if 'first' in col_map else ''
                last = str(row.get(col_map.get('last'), '')).strip() if 'last' in col_map else ''
                phone = str(row.get(col_map.get('phone'), '')).strip() if 'phone' in col_map else ''
                
                # Check if exists
                if email in self.riders:
                    stats['skipped'] += 1 # Already exists, maybe update later?
                    continue
                
                # Add to DB
                # Note: We pass empty strings for socials unless we want to try mapping them too
                success = self.add_new_rider(email, first, last, fb_url="", ig_url="")
                if success:
                    stats['added'] += 1
                else:
                    stats['errors'] += 1
                    
        except Exception as e:
            print(f"Import Error: {e}")
            stats['errors'] += 1
            
        return stats

    def cleanup_duplicates(self) -> int:
        """Scan Rider Database.csv for duplicates and merge them"""
        filename = "Rider Database.csv"
        filepath = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(filepath):
            return 0
            
        try:
            df = pd.read_csv(filepath)
            original_count = len(df)
            
            # Normalize Email for grouping
            if 'Email Address' not in df.columns:
                return 0
                
            df['Email_Lower'] = df['Email Address'].astype(str).str.lower().str.strip()
            
            # Define aggregation logic: take first non-null
            def first_valid(series):
                return series.dropna().iloc[0] if not series.dropna().empty else ""
                
            # Group and Merge
            # We want to keep all columns, merging logic for each
            agg_dict = {col: first_valid for col in df.columns if col != 'Email_Lower'}
            
            deduped = df.groupby('Email_Lower', as_index=False).agg(agg_dict)
            
            # Remove temp column
            # deduped = deduped.drop(columns=['Email_Lower']) # Not needed if we didn't include it in agg
            
            # Logic check: groupby produces 'Email_Lower' as a column now because as_index=False
            # But we aggregated everything else. The original 'Email Address' is in the agg_dict.
            # So 'Email_Lower' is the unique key. 
            # We should drop 'Email_Lower' and rely on the retained 'Email Address'.
            
            deduped = deduped.drop(columns=['Email_Lower'])
            
            final_count = len(deduped)
            removed = original_count - final_count
            
            if removed > 0:
                # Save back
                deduped.to_csv(filepath, index=False, encoding='utf-8-sig')
                self.reload_data()
                
            return removed
            
        except Exception as e:
            print(f"Cleanup Error: {e}")
            return 0

    def generate_outreach_message(self, result: Dict, event_name: str) -> str:
        return self.race_manager.generate_outreach_message(result, event_name)

    def migrate_rider_to_airtable(self, email: str) -> bool:
        """
        Sync rider to Airtable and DELETE from GSheets to migrate.
        """
        email = email.lower().strip()
        rider = self.riders.get(email)
        if not rider: return False
        
        # 1. Sync to Airtable
        synced = False
        if self.airtable:
            try:
                record = {
                     "Email": rider.email,
                     "First Name": rider.first_name,
                     "Last Name": rider.last_name,
                     "FB URL": rider.facebook_url,
                     "IG URL": rider.instagram_url,
                     "Championship": rider.championship,
                     "Stage": rider.current_stage.value,
                     "Phone": rider.phone,
                     "Notes": rider.notes
                }
                # Optional fields
                if rider.sale_value: record["Revenue"] = rider.sale_value
                if rider.follow_up_date:
                    record["Follow Up Date"] = rider.follow_up_date.strftime('%Y-%m-%d')
                
                # Upsert
                self.airtable.upsert_rider(record)
                synced = True
                print(f"Migrated {rider.first_name} to Airtable.")
            except Exception as e:
                print(f"Migration Sync Error: {e}")
                return False
        
        # 2. Delete from GSheets (if synced)
        if synced:
            if "sheets" in st.secrets and "rider_db" in st.secrets["sheets"]:
                url = st.secrets["sheets"]["rider_db"]
                
                # Attempt delete by Email first
                deleted, msg = gsheets_loader.delete_row_by_email(url, email)
                
                if deleted:
                    print(f"Deleted from GSheet: {msg}")
                else:
                    # Fallback: Delete by Name for Social-Only (or if email not found)
                    # Often "no_email_" or slug IDs won't be in the Email column
                    print(f"Email delete failed/skipped ({msg}). Trying Name match...")
                    
                    deleted_name, msg_name = gsheets_loader.delete_row_by_name(url, rider.first_name, rider.last_name)
                    
                    if deleted_name:
                         print(f"Deleted from GSheet (Name Match): {msg_name}")
                    else:
                         print(f"Failed to delete from GSheet: {msg_name}")
        
        return synced

    def add_new_rider(self, email: str, first_name: str, last_name: str, fb_url: str, ig_url: str = "", championship: str = "", notes: str = None, follow_up_date: datetime = None) -> bool:
        """Add a new rider to the database"""
        # Save to Local CSV first (Redundancy)
        success = self.data_loader.add_new_rider_to_db(email, first_name, last_name, fb_url, ig_url=ig_url, championship=championship, notes=notes, follow_up_date=follow_up_date)
        
        if success:
            # Update In-Memory
            self.riders[email.lower()] = self.data_loader._get_or_create_rider(email)
            rider = self.riders[email.lower()]
            
            # Update fields if provided (and not handled by lower level)
            # (DataLoader handles most, but ensuring manual fields are set)
            if notes: rider.notes = notes
            if championship: rider.championship = championship
            if follow_up_date: rider.follow_up_date = follow_up_date
            
            # TRIGGER MIGRATION (Sync to Airtable + Delete from GSheet)
            self.migrate_rider_to_airtable(email)
                    
        return success

    def update_rider_stage(self, email: str, new_stage: FunnelStage, sale_value: Optional[float] = None):
        """Manually update a rider's stage"""
        # Save to CSV and update in-memory
        if self.data_loader.save_manual_update(email, new_stage.value):
            rider = self.riders.get(email.lower())
            if rider:
                rider.current_stage = new_stage
                
                # Logic: If moving to OUTREACH/MESSAGED, set outreach_date = now
                # We update it even if it exists, because a MANUAL move implies a new action/re-engagement.
                # This ensures they show up in "Current Month" dashboard.
                if new_stage in [FunnelStage.MESSAGED, FunnelStage.OUTREACH]:
                    rider.outreach_date = datetime.now()
                
                # Ensure outreach_date is set for subsequent stages if skipped/missing
                elif new_stage in [FunnelStage.REPLIED, FunnelStage.LINK_SENT, FunnelStage.BLUEPRINT_LINK_SENT]:
                    if not rider.outreach_date:
                        rider.outreach_date = datetime.now()
                    
                elif new_stage == FunnelStage.STRATEGY_CALL_BOOKED and not rider.strategy_call_booked_date:
                    rider.strategy_call_booked_date = datetime.now()
                elif new_stage == FunnelStage.SALE_CLOSED:
                    rider.sale_closed_date = datetime.now()
                    if sale_value is not None:
                         rider.sale_value = sale_value
                
                # Save revenue if applicable
                if sale_value:
                    self.data_loader.save_revenue(email, sale_value)
                
                # TRIGGER MIGRATION
                self.migrate_rider_to_airtable(email)
                
                # --- AUTO-INCREMENT DAILY STATS ---
                # Ensure the dashboard metrics reflect this action immediately
                if new_stage == FunnelStage.MESSAGED:
                    # Guess channel based on URLs (or default to FB if both or neither, usually FB is primary)
                    if rider.instagram_url and not rider.facebook_url:
                        self.daily_stats.increment_ig()
                    else:
                        self.daily_stats.increment_fb()
                        
                elif new_stage == FunnelStage.LINK_SENT:
                    self.daily_stats.increment_link()
        
        # Recalculate conversion rates as data changed
        self._calculate_conversion_rates()

    # ==========================================
    # DAILY DASHBOARD METRICS
    # ==========================================
    
    def get_daily_metrics(self, target_date: Optional[datetime.date] = None) -> Dict:
        """Get counts of activities for a specific date (default Today)"""
        if not target_date:
            target_date = datetime.now().date()
            
        # 1. Get Manual Stats
        manual = self.daily_stats.get_stats_for_date(target_date)
            
        metrics = {
            'outreach_sent': 0, # Legacy total
            # Manual Metrics
            'fb_sent': manual.fb_messages_sent,
            'ig_sent': manual.ig_messages_sent,
            'links_sent': manual.links_sent,
            
            # Automated Metrics
            'new_registered': 0,
            'day1_completed': 0,
            'day2_completed': 0,
            'calls_booked': 0,
            'sales_closed': 0
        }
        
        for r in self.riders.values():
            # Check each date field
            if r.outreach_date and r.outreach_date.date() == target_date:
                metrics['outreach_sent'] += 1
            if r.registered_date and r.registered_date.date() == target_date:
                metrics['new_registered'] += 1
            if r.day1_complete_date and r.day1_complete_date.date() == target_date:
                metrics['day1_completed'] += 1
            if r.day2_complete_date and r.day2_complete_date.date() == target_date:
                metrics['day2_completed'] += 1
            if r.strategy_call_booked_date and r.strategy_call_booked_date.date() == target_date:
                metrics['calls_booked'] += 1
            if r.sale_closed_date and r.sale_closed_date.date() == target_date:
                metrics['sales_closed'] += 1
                
        return metrics

    def get_stalled_riders(self, days_threshold: int = 1) -> Dict[str, List[Dict]]:
        """Identify riders stuck in a stage longer than threshold"""
        stalled = {
            'registered_no_start': [], # Reg -> Day 1 stuck
            'day1_no_day2': [],        # Day 1 -> Day 2 stuck
            'day2_no_call': [],        # Day 2 -> Call stuck
            'outreach_no_reply': []    # Outreach -> stuck (maybe too noisy?)
        }
        
        for r in self.riders.values():
            days_in = r.days_in_current_stage
            if days_in is None or days_in < days_threshold:
                continue
                
            info = {
                'name': r.full_name or r.email,
                'email': r.email,
                'days': days_in,
                'stage': r.current_stage.value,
                'fb': r.facebook_url
            }

            if r.current_stage == FunnelStage.REGISTERED:
                stalled['registered_no_start'].append(info)
            elif r.current_stage == FunnelStage.DAY1_COMPLETE:
                stalled['day1_no_day2'].append(info)
            elif r.current_stage == FunnelStage.DAY2_COMPLETE:
                stalled['day2_no_call'].append(info)
            elif r.current_stage == FunnelStage.OUTREACH:
                stalled['outreach_no_reply'].append(info)
                
        return stalled

    def get_revenue_metrics(self) -> Dict:
        """Calculate revenue progress"""
        target = float(self.calculator.config.MONTHLY_REVENUE_TARGET)
        actual = 0.0
        pipeline_value = 0.0
        
        program_cost = 4000.0
        
        for r in self.riders.values():
            if r.current_stage == FunnelStage.SALE_CLOSED:
                actual += r.sale_value if r.sale_value else program_cost
            elif r.current_stage == FunnelStage.STRATEGY_CALL_BOOKED:
                pipeline_value += program_cost * 0.25 
                
        return {
            'target': target,
            'actual': actual,
            'pipeline': pipeline_value,
            'progress_pct': (actual / target) * 100 if target > 0 else 0
        }

    def _calculate_conversion_rates(self):
        """Calculate actual conversion rates from data"""
        stage_counts = self.get_stage_counts()

        # Only update if we have meaningful data
        if stage_counts['registered'] > 10:
            rates = {}

            if stage_counts['registered'] > 0:
                rates['registration_to_day1'] = (
                    stage_counts['day1_complete'] / stage_counts['registered']
                )

            if stage_counts['day1_complete'] > 0:
                rates['day1_to_day2'] = (
                    stage_counts['day2_complete'] / stage_counts['day1_complete']
                )

            if stage_counts['day2_complete'] > 0:
                rates['day2_to_strategy_call'] = (
                    stage_counts['strategy_call_booked'] / stage_counts['day2_complete']
                )

            self.calculator.update_conversion_rates(rates)

    def get_stage_counts(self) -> Dict[str, int]:
        """Get count of riders at each stage"""
        counts = defaultdict(int)

        for rider in self.riders.values():
            stage_name = rider.current_stage.value
            counts[stage_name] += 1

            # Also count total who reached each stage (not just current)
            if rider.registered_date:
                counts['total_registered'] += 1
            if rider.day1_complete_date:
                counts['total_day1'] += 1
            if rider.day2_complete_date:
                counts['total_day2'] += 1
            if rider.strategy_call_booked_date:
                counts['total_calls_booked'] += 1

        # Map to simpler names
        return {
            'registered': counts['total_registered'],
            'day1_complete': counts['total_day1'],
            'day2_complete': counts['total_day2'],
            'strategy_call_booked': counts['total_calls_booked'],
            'current_registered': counts['registered'],
            'current_day1': counts['day1_complete'],
            'current_day2': counts['day2_complete'],
            'current_calls': counts['strategy_call_booked'],
        }

    def get_stage_counts_by_month(self, year: int, month: int) -> Dict[str, int]:
        """Get counts for a specific month (MTD Actuals)"""
        counts = defaultdict(int)
        
        for rider in self.riders.values():
            # Helper to check date match
            def is_in_month(dt):
                return dt and dt.year == year and dt.month == month

            if is_in_month(rider.registered_date):
                counts['registered'] += 1
            if is_in_month(rider.day1_complete_date):
                counts['day1_complete'] += 1
            if is_in_month(rider.day2_complete_date):
                counts['day2_complete'] += 1
            if is_in_month(rider.strategy_call_booked_date):
                counts['strategy_call_booked'] += 1
                
        return counts

    def get_funnel_summary(self) -> str:
        """Generate a text summary of the funnel"""
        counts = self.get_stage_counts()
        targets = self.calculator.calculate_targets()

        lines = [
            "=" * 60,
            "CAMINO COACHING - FUNNEL DASHBOARD",
            f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "=" * 60,
            "",
            "📊 MONTHLY TARGETS",
            "-" * 40,
            f"Revenue Target:      £{targets.monthly_revenue:,.0f}",
            f"Sales Needed:        {targets.monthly_sales}",
            f"Strategy Calls:      {targets.monthly_strategy_calls}",
            f"Day 2 Completions:   {targets.monthly_day2_completions}",
            f"Day 1 Completions:   {targets.monthly_day1_completions}",
            f"Registrations:       {targets.monthly_registrations}",
            f"Total Outreach:      {targets.monthly_outreach}",
            "",
            "📈 CURRENT FUNNEL STATE",
            "-" * 40,
            f"Total Riders in System:   {len(self.riders)}",
            f"Registered:               {counts['registered']}",
            f"Day 1 Complete:           {counts['day1_complete']}",
            f"Day 2 Complete:           {counts['day2_complete']}",
            f"Strategy Calls Booked:    {counts['strategy_call_booked']}",
            "",
            "📉 CONVERSION RATES (Actual)",
            "-" * 40,
        ]

        for rate_name, rate_value in self.calculator.conversion_rates.items():
            lines.append(f"{rate_name}: {rate_value*100:.1f}%")

        # Add rescue needed section
        rescue_needed = self.rescue_manager.get_riders_needing_rescue(list(self.riders.values()))

        lines.extend([
            "",
            "🆘 RIDERS NEEDING RESCUE",
            "-" * 40,
            f"Day 1 Rescue Needed:          {len(rescue_needed['day1_rescue'])}",
            f"Day 2 Rescue Needed:          {len(rescue_needed['day2_rescue'])}",
            f"Strategy Call Rescue Needed:  {len(rescue_needed['strategy_call_rescue'])}",
        ])

        # Add daily action items
        lines.extend([
            "",
            "📋 DAILY TARGETS",
            "-" * 40,
            f"Outreach Messages:   {targets.daily_outreach} per day",
            f"  - Email:           {targets.daily_outreach // 3}",
            f"  - Facebook DM:     {targets.daily_outreach // 3}",
            f"  - Instagram DM:    {targets.daily_outreach // 3}",
            "",
            "=" * 60,
        ])

        return "\n".join(lines)

    def get_rescue_actions(self) -> str:
        """Get list of rescue actions needed today"""
        rescue_needed = self.rescue_manager.get_riders_needing_rescue(list(self.riders.values()))

        lines = [
            "=" * 60,
            "🆘 RESCUE ACTIONS NEEDED",
            "=" * 60,
        ]

        for rescue_type, riders in rescue_needed.items():
            if not riders:
                continue

            lines.append(f"\n{rescue_type.upper().replace('_', ' ')} ({len(riders)} riders)")
            lines.append("-" * 40)

            for rider in riders[:10]:  # Show top 10
                days = rider.days_in_current_stage
                lines.append(f"  • {rider.full_name} ({rider.email})")
                lines.append(f"    Stuck for: {days} days")

                # Get message preview
                msg = self.rescue_manager.get_rescue_message(rescue_type, rider, 'dm')
                preview = msg['body'][:100] + "..." if len(msg['body']) > 100 else msg['body']
                lines.append(f"    Message: {preview}")
                lines.append("")

            if len(riders) > 10:
                lines.append(f"  ... and {len(riders) - 10} more")

        return "\n".join(lines)

    def export_daily_report(self, filename: str = None) -> str:
        """Export a daily report to file"""
        if not filename:
            filename = f"daily_report_{datetime.now().strftime('%Y%m%d')}.txt"

        filepath = os.path.join(self.data_dir, filename)

        report = self.get_funnel_summary() + "\n\n" + self.get_rescue_actions()

        with open(filepath, 'w') as f:
            f.write(report)

        return filepath


# =============================================================================
# OUTREACH TRACKER
# =============================================================================

@dataclass
class OutreachRecord:
    """Record of an outreach attempt"""
    date: datetime
    channel: OutreachChannel
    rider_email: str
    rider_name: str
    message_sent: bool = True
    response_received: bool = False
    registered: bool = False
    notes: str = ""


class OutreachTracker:
    """Track daily outreach activities"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.outreach_file = os.path.join(data_dir, 'outreach_log.csv')
        self.records: List[OutreachRecord] = []
        self._load_records()

    def _load_records(self):
        """Load existing outreach records"""
        if not os.path.exists(self.outreach_file):
            return

        with open(self.outreach_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    record = OutreachRecord(
                        date=datetime.strptime(row['date'], '%Y-%m-%d %H:%M:%S'),
                        channel=OutreachChannel(row['channel']),
                        rider_email=row['rider_email'],
                        rider_name=row['rider_name'],
                        message_sent=row['message_sent'].lower() == 'true',
                        response_received=row['response_received'].lower() == 'true',
                        registered=row['registered'].lower() == 'true',
                        notes=row.get('notes', '')
                    )
                    self.records.append(record)
                except (KeyError, ValueError):
                    continue

    def _save_records(self):
        """Save all records to file"""
        with open(self.outreach_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'date', 'channel', 'rider_email', 'rider_name',
                'message_sent', 'response_received', 'registered', 'notes'
            ])
            writer.writeheader()

            for record in self.records:
                writer.writerow({
                    'date': record.date.strftime('%Y-%m-%d %H:%M:%S'),
                    'channel': record.channel.value,
                    'rider_email': record.rider_email,
                    'rider_name': record.rider_name,
                    'message_sent': str(record.message_sent),
                    'response_received': str(record.response_received),
                    'registered': str(record.registered),
                    'notes': record.notes
                })

    def add_outreach(self,
                     channel: OutreachChannel,
                     rider_email: str,
                     rider_name: str,
                     notes: str = "") -> OutreachRecord:
        """Record a new outreach attempt"""
        record = OutreachRecord(
            date=datetime.now(),
            channel=channel,
            rider_email=rider_email,
            rider_name=rider_name,
            notes=notes
        )
        self.records.append(record)
        self._save_records()
        return record

    def get_today_count(self) -> Dict[str, int]:
        """Get outreach count for today by channel"""
        today = datetime.now().date()
        counts = {'email': 0, 'facebook_dm': 0, 'instagram_dm': 0, 'total': 0}

        for record in self.records:
            if record.date.date() == today:
                counts[record.channel.value] += 1
                counts['total'] += 1

                counts['total'] += 1

        return counts
    
    # --- AUTOMATION METHODS ---
    def increment_fb(self):
        """Add +1 to Today's FB Messages"""
        self.update_stats(datetime.now().date(), fb_messages_sent=1)
        
    def increment_ig(self):
        """Add +1 to Today's IG Messages"""
        self.update_stats(datetime.now().date(), ig_messages_sent=1)
        
    def increment_link(self):
        """Add +1 to Today's Links Sent"""
        self.update_stats(datetime.now().date(), links_sent=1)

    def get_mtd_total(self, stat_name: str) -> int:
        """Calculate Month-To-Date total for a manual stat"""
        total = 0
        today = datetime.now()
        
        # Iterate all loaded stats
        for date_key, stats in self.stats.items():
            # Check if same month and year
            if date_key.year == today.year and date_key.month == today.month:
                total += getattr(stats, stat_name, 0)
                
        return total

    def get_week_count(self) -> Dict[str, int]:
        """Get outreach count for this week"""
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())

        counts = {'email': 0, 'facebook_dm': 0, 'instagram_dm': 0, 'total': 0}

        for record in self.records:
            if record.date >= week_start:
                counts[record.channel.value] += 1
                counts['total'] += 1

        return counts

    def get_month_count(self) -> Dict[str, int]:
        """Get outreach count for this month"""
        today = datetime.now()
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        counts = {'email': 0, 'facebook_dm': 0, 'instagram_dm': 0, 'total': 0}

        for record in self.records:
            if record.date >= month_start:
                counts[record.channel.value] += 1
                counts['total'] += 1

        return counts

    def get_conversion_rate(self, period_days: int = 30) -> float:
        """Calculate outreach to registration conversion rate"""
        cutoff = datetime.now() - timedelta(days=period_days)

        total = 0
        registered = 0

        for record in self.records:
            if record.date >= cutoff:
                total += 1
                if record.registered:
                    registered += 1

        if total == 0:
            return 0.0

        return registered / total


# =============================================================================
# MAIN CLI INTERFACE
# =============================================================================

def print_header():
    """Print application header"""
    print("""
╔════════════════════════════════════════════════════════════╗
║       CAMINO COACHING - RIDER FUNNEL MANAGER              ║
║                                                            ║
║  Target: £15,000/month | Programme: £4,000                ║
╚════════════════════════════════════════════════════════════╝
    """)


def main():
    """Main entry point"""
    import sys

    # Default data directory
    data_dir = os.path.dirname(os.path.abspath(__file__))

    print_header()

    # Initialize dashboard
    print("Loading data...")
    dashboard = FunnelDashboard(data_dir)
    outreach_tracker = OutreachTracker(data_dir)

    print(f"Loaded {len(dashboard.riders)} riders from data files.\n")

    # Display summary
    print(dashboard.get_funnel_summary())
    print("\n")
    print(dashboard.get_rescue_actions())

    # Show outreach progress
    today_outreach = outreach_tracker.get_today_count()
    week_outreach = outreach_tracker.get_week_count()
    targets = dashboard.calculator.calculate_targets()

    print("\n" + "=" * 60)
    print("📤 OUTREACH PROGRESS")
    print("=" * 60)
    print(f"\nToday: {today_outreach['total']}/{targets.daily_outreach} messages")
    print(f"  Email:       {today_outreach['email']}")
    print(f"  Facebook:    {today_outreach['facebook_dm']}")
    print(f"  Instagram:   {today_outreach['instagram_dm']}")
    print(f"\nThis Week: {week_outreach['total']}/{targets.weekly_outreach} messages")

    remaining_today = targets.daily_outreach - today_outreach['total']
    if remaining_today > 0:
        print(f"\n⚠️  You need {remaining_today} more outreach messages today!")
    else:
        print(f"\n✅ Daily outreach target met!")


if __name__ == "__main__":
    main()

# =============================================================================
# RACE RESULT MANAGER (Restored)
# =============================================================================
class SocialFinder:
    """Find social media profiles and generate Deep DM Links"""
    
    def find_socials(self, name: str, context: str = "") -> Dict[str, str]:
        """
        Search for social media profiles using multi-level strategy.
        Returns dict of {platform: url}
        """
        # Level 1: Core Racing Search
        # Level 2: Social Specific
        queries = [
            f'"{name}" site:instagram.com ("racing" OR "racer" OR "motorsport")',
            f'"{name}" site:facebook.com ("motorcycle" OR "racing")',
            f'"{name}" {context} racing social media',
            f'"{name}" AND ("competitor" OR "race results")'
        ]
        
        found = {}
        
        try:
            from googlesearch import search
            
            # Use the most specific one first
            base_query = queries[0] 
            
            # Search top 15 results
            results = list(search(base_query, num_results=15, advanced=True))
            
            for result in results:
                url = result.url
                lower_url = url.lower()
                
                if "facebook.com" in lower_url and "public" not in lower_url and "posts" not in lower_url:
                    if "facebook_url" not in found:
                        found['facebook_url'] = url
                        
                elif "instagram.com" in lower_url:
                    if "instagram_url" not in found:
                        # Clean out some junk params if needed
                        found['instagram_url'] = url
                        
                elif "linkedin.com/in" in lower_url:
                    if "linkedin_url" not in found:
                        found['linkedin_url'] = url
                        
        except ImportError:
            print("googlesearch-python not installed")
        except Exception as e:
            print(f"Search error: {e}")
            
        return found

    def clean_social_url(self, url: str) -> Optional[str]:
        """Extract username/handle from a raw URL"""
        if not url: return None
        
        # Basic cleanup
        clean = url.strip().rstrip('/')
        
        # Remove query params
        if '?' in clean:
            clean = clean.split('?')[0]
            
        return clean

    def generate_deep_dm_link(self, platform: str, url: str, message: str = "") -> Optional[str]:
        """
        Generate a direct 'Mobile First' deep link for DMs.
        - Facebook: m.me/{username}
        - Instagram: ig.me/m/{username}
        """
        import urllib.parse
        
        if not url: return None
        
        clean_url = self.clean_social_url(url)
        username = clean_url.split('/')[-1]
        
        # Safety check: if username is 'profile.php', we might need ID parsing (skip for now)
        if 'profile.php' in username:
            return None 
            
        encoded_msg = urllib.parse.quote(message)
        
        if platform == 'facebook':
            # https://m.me/<USERNAME>?text=<MESSAGE>
            return f"https://m.me/{username}?text={encoded_msg}"
            
        elif platform == 'instagram':
            # https://ig.me/m/<USERNAME>?text=<MESSAGE>
            return f"https://ig.me/m/{username}?text={encoded_msg}"
            
        return None

    def generate_deep_search_links(self, name: str, event_name: str = "") -> Dict[str, str]:
        """
        Generate Google Dork URLs for manual Deep Search.
        Based on User's Level 1-4 Operators.
        """
        import urllib.parse
        
        def make_link(query):
            return f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            
        links = {}
        
        # Level 1: Core Discovery
        links['🔍 Core Discovery'] = make_link(f'"{name}" AND ("racing" OR "racer" OR "motorsport" OR "bike")')
        
        # Level 2: Socials (Direct Platform Search preferred by User)
        # Facebook: Direct search (shows mutuals)
        links['👥 Facebook Direct'] = f"https://www.facebook.com/search/people/?q={urllib.parse.quote(name)}"
        
        # Instagram: No reliable web search URL, so we link to Home for pasting
        links['📸 Instagram Direct'] = "https://www.instagram.com/"
        
        # Keep Google backups just in case
        links['(Backup) IG Google'] = make_link(f'"{name}" site:instagram.com ("racing" OR "track day" OR "moto")')
        
        # Level 3: Context / Event
        if event_name:
            links['🏁 Event check'] = make_link(f'"{name}" AND "{event_name}" ("race results" OR "competitor")')
            
        # Level 4: Validation (Associations)
        links['📋 Racing Org Check'] = make_link(f'"{name}" AND ("CVMA" OR "WERA" OR "ASMA" OR "CRA")')
        links['⏱️ Lap Times'] = make_link(f'"{name}" AND ("lap times" OR "race monitor" OR "mylaps")')
        
        return links

    def generate_search_link(self, name: str) -> str:
        # Legacy fallback
        return self.generate_deep_search_links(name)['🔍 Core Discovery']


class RaceResultManager:
    """Manages race result analysis and outreach generation"""

    def __init__(self, data_loader: DataLoader):
        self.data_loader = data_loader
        self.riders = data_loader.riders
        self.social_finder = SocialFinder()
        self.circuit_file = os.path.join(data_loader.data_dir, "race_circuits.json")
        self.circuits = self._load_circuits()

    def _load_circuits(self) -> List[str]:
        if os.path.exists(self.circuit_file):
            try:
                with open(self.circuit_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_circuit(self, name: str):
        if not name: return
        name = name.strip()
        if name not in self.circuits:
            self.circuits.append(name)
            self.circuits.sort()
            with open(self.circuit_file, 'w') as f:
                json.dump(self.circuits, f)
                
    def get_all_circuits(self) -> List[str]:
        return self.circuits

    def match_rider(self, raw_name: str) -> Optional[Rider]:
        """Attempt to match a raw name from results to a database rider"""
        if not raw_name:
            return None
            
        clean_raw = raw_name.lower().strip()
        
        # Helper: remove common race result noise (e.g. "(G)", numbers)
        # For now just simple whitespace
        
        # 1. Exact Match (Direct)
        for email, rider in self.riders.items():
            if rider.full_name.lower() == clean_raw:
                return rider
                
        # 2. Try "Last, First" swap -> "First Last"
        if ',' in clean_raw:
            parts = clean_raw.split(',')
            if len(parts) >= 2:
                swapped = f"{parts[1].strip()} {parts[0].strip()}"
                for email, rider in self.riders.items():
                   if rider.full_name.lower() == swapped:
                       return rider
                       
        # 3. Token-Based Match (Stricter)
        # Require multiple parts to match to avoid "Joshua" matching "Joshua Ferrer"
        # Logic: Both First and Last name tokens should be present
        
        raw_tokens = set(clean_raw.split())
        
        for email, rider in self.riders.items():
            # SANITY CHECK: Ignore corrupt riders with massive names (e.g. concatenated strings)
            if len(rider.full_name) > 60:
                continue

            db_name = rider.full_name.lower().strip()
            db_tokens = set(db_name.split())
            
            # If names are identical (handled by 1), but let's re-verify intersection
            if not db_tokens: continue
            
            common = raw_tokens.intersection(db_tokens)
            
            # CRITERIA:
            # 1. If DB Name is longer than 1 word (e.g. "Joshua Ferrer"), we need at least 2 matches (First + Last)
            # 2. If DB Name is 1 word, we need exact match (handled above) or complete inclusion? 
            #    Actually user said "First and Last Name must match", implying single names shouldn't match multi-names loosely.
            
            if len(db_tokens) >= 2:
                # Require at least 2 tokens to match (First & Last)
                # This prevents "Joshua" (input) matching "Joshua Ferrer" (DB) -> No, "Joshua" input has 1 token.
                # This prevents "Joshua Ferrer" (input) matching "Joshua Other" (DB) -> Common is 1 ("Joshua").
                if len(common) >= 2:
                    return rider
            
            # Special case: If input has only 1 name, we generally shouldn't match it to a 2-name person 
            # unless it's a nickname field or exact match (handled above).
            
            # Fallback: What if input is "Josh Ferrer" vs "Joshua Ferrer"?
            # That requires phonetic/substring or nickname matching. 
            # For now, sticking to the user's request: "First and Last name must match".
            # The token intersection handles "Joshua Ferrer" vs "Ferrer Joshua".
            
        return None

    def process_race_results(self, raw_names: List[str], event_name: str) -> List[Dict]:
        """Process a list of names and return match status"""
        results = []
        for name in raw_names:
            if not name.strip():
                continue
            
            # Remove trailing position numbers or gaps if simple split
            # Often PDF extracts might be "Name 1:23.456"
            # We assume the input is relatively clean list of names
            
            clean_name = name.strip()
            match = self.match_rider(clean_name)
            
            status = "match_found" if match else "new_prospect"
            
            # Determine appropriate stage/context
            current_stage = match.current_stage.value if match else "New"
            
            results.append({
                "original_name": clean_name,
                "match_status": status,
                "match": match, # Internal object
                "matched_email": match.email if match else None,
                "facebook_url": match.facebook_url if match else None,
                "current_stage": current_stage
            })
        return results

    def generate_outreach_message(self, result: Dict, event_name: str) -> str:
        """Generate a context-aware message based on User Templates"""
        name = result['original_name']
        match = result['match']
        
        # Split first name
        first_name = name.split(' ')[0].title()
        if match and match.first_name:
             first_name = match.first_name
             
        # TEMPLATE: SEQUENCE 1 (Qualifying Struggle -> Free Training)
        # Context: saw them race, maybe qualified well but finished lower, or just general outreach
        # We will adapt the "Opening" message from the PDF
        
        if result['match_status'] == 'match_found' and match:
            # Context: Existing Contact
            if match.race_weekend_review_status == 'completed':
                return f"Hey {first_name}, great to see you out at {event_name}! Saw you already did your review - how are you feeling about the progress since then?"
            else:
                # Dynamic Message for Existing (similar to new but acknowledging connection?)
                # For now using the same friendly pattern but maybe slightly warmer?
                # Sticking to the requested template:
                greeting = random.choice(["Hey", "Hi", "Hello"])
                closing = random.choice(["How did it go?", "How was it for you?", "How was your race weekend?"])
                
                return f"{greeting} {first_name}, I see you were out at {event_name} at the weekend. {closing}"
        else:
             # Context: Cold / New
             greeting = random.choice(["Hey", "Hi", "Hello"])
             closing = random.choice(["How did it go?", "How was it for you?", "How was your race weekend?"])
             
             return f"{greeting} {first_name}, I see you were out at {event_name} at the weekend. {closing}"

    def find_socials_for_prospect(self, name: str, context: str) -> Dict[str, str]:
        """Find socials for a prospect"""
        return self.social_finder.find_socials(name, context)
    
    def get_manual_search_link(self, name: str) -> str:
        return self.social_finder.generate_search_link(name)


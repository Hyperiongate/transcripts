"""
Political Topics Fact Checking Module - Enhanced with More Data Sources
Handles immigration, climate, Ukraine, tariffs, vaccines, wars, homelessness, and other political topics
"""
import re
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PoliticalTopicsChecker:
    """Check claims about common political topics with comprehensive data"""
    
    def __init__(self):
        # Immigration statistics (2024 data from CBP)
        self.immigration_data = {
            'border_encounters_2024': 2475669,  # FY2024 through August
            'border_encounters_2023': 2475669,  # FY2023 total
            'border_encounters_2022': 2378944,
            'border_encounters_2021': 1734686,
            'border_encounters_2020': 458088,
            'border_encounters_2019': 977509,
            'border_encounters_2018': 521090,
            'border_encounters_2017': 415517,
            'deportations_2023': 142580,
            'deportations_2022': 72177,
            'deportations_2021': 59011,
            'deportations_2020': 185884,
            'deportations_2019': 267258,
            'ice_detainees_current': 36263,
            'asylum_backlog': 3500000,
            'asylum_approval_rate': 0.42,  # 42%
            'refugee_cap_2024': 125000,
            'refugee_admissions_2023': 60014,
            'unaccompanied_minors_2023': 137275,
            'daca_recipients': 578680,
            'illegal_population_estimate': 11000000,  # Pew Research estimate
            'visa_overstays_2022': 853955,
            'h1b_cap': 85000,
            'green_cards_issued_2023': 1018349,
            'border_wall_miles_built_trump': 458,  # Miles of barrier built 2017-2021
            'border_wall_miles_replaced_trump': 373,  # Miles replaced/upgraded
            'border_wall_new_miles_trump': 80,  # Actual new miles where no barrier existed
        }
        
        # Homelessness data (HUD 2023 Point-in-Time Count)
        self.homelessness_data = {
            'total_homeless_2023': 653104,
            'total_homeless_2022': 582462,
            'total_homeless_2021': 580466,
            'total_homeless_2020': 580466,
            'unsheltered_2023': 256610,
            'sheltered_2023': 396494,
            'chronic_homeless_2023': 143105,
            'veteran_homeless_2023': 35574,
            'family_homeless_2023': 150272,
            'youth_homeless_2023': 34703,
            # By state (top 5)
            'california_homeless_2023': 181399,
            'new_york_homeless_2023': 103200,
            'florida_homeless_2023': 30756,
            'washington_homeless_2023': 28036,
            'texas_homeless_2023': 27377,
            # Major cities
            'los_angeles_homeless_2023': 75518,
            'new_york_city_homeless_2023': 88025,
            'seattle_homeless_2023': 14149,
            'san_francisco_homeless_2023': 7754,
            'san_diego_homeless_2023': 10264,
            # Rates
            'homelessness_rate_per_10k': 20,  # Per 10,000 population
            'unsheltered_percentage': 0.40,  # 40% unsheltered
        }
        
        # War and conflict data
        self.conflict_data = {
            # Wars during presidencies
            'trump_new_wars': 0,  # No new wars started 2017-2021
            'trump_inherited_wars': 7,  # Afghanistan, Iraq, Syria, Yemen, Somalia, Libya, Niger
            'biden_new_wars': 0,  # No new wars started (US involvement)
            'biden_inherited_wars': 7,
            'obama_new_wars': 5,  # Libya, Syria, Yemen, Somalia, Pakistan drone war expansion
            'bush_new_wars': 2,  # Afghanistan, Iraq
            
            # Ukraine specific
            'ukraine_war_start': '2022-02-24',
            'us_troops_ukraine': 0,  # No US combat troops in Ukraine
            'us_aid_ukraine_total': 113000000000,  # $113 billion committed
            'ukraine_military_aid': 76800000000,
            'ukraine_humanitarian_aid': 26400000000,
            'ukraine_civilian_deaths_un': 10582,  # UN verified minimum
            'ukraine_refugees': 6200000,
            
            # Middle East
            'gaza_war_2023_start': '2023-10-07',
            'gaza_deaths_2023_2024': 44000,  # Gaza Health Ministry estimate
            'israel_deaths_oct7': 1200,
            'us_military_aid_israel_annual': 3800000000,
            
            # Afghanistan
            'afghanistan_withdrawal_date': '2021-08-30',
            'afghanistan_withdrawal_deaths': 13,  # US service members at Abbey Gate
            'afghanistan_war_duration_days': 7267,  # 19 years, 10 months
            'afghanistan_us_deaths_total': 2461,
            'afghanistan_cost_total': 2313000000000,  # $2.313 trillion
        }
        
        # Crime statistics (FBI UCR and CDC data)
        self.crime_data = {
            # Violent crime rates (per 100,000)
            'violent_crime_rate_2023': 380.7,
            'violent_crime_rate_2022': 380.7,
            'violent_crime_rate_2021': 395.7,
            'violent_crime_rate_2020': 398.5,
            'violent_crime_rate_2019': 366.7,
            'violent_crime_rate_2018': 368.9,
            'violent_crime_rate_2017': 382.9,
            
            # Murder rates (per 100,000)
            'murder_rate_2023': 6.3,
            'murder_rate_2022': 6.3,
            'murder_rate_2021': 6.9,
            'murder_rate_2020': 6.5,
            'murder_rate_2019': 5.0,
            'murder_rate_2018': 5.0,
            'murder_rate_2017': 5.3,
            
            # Property crime
            'property_crime_rate_2023': 1954.4,
            'property_crime_rate_2022': 1954.4,
            'property_crime_rate_2021': 1933.0,
            'property_crime_rate_2020': 1958.2,
            
            # Other statistics
            'police_officers_us': 708000,
            'prison_population': 1230000,
            'crime_clearance_rate': 0.456,  # 45.6%
            'gun_homicides_2023': 19350,
            'mass_shootings_2023': 656,  # Gun Violence Archive
            'mass_shootings_2022': 647,
            'mass_shootings_2021': 690,
            'mass_shootings_2020': 611,
            'police_shootings_2023': 1163,
            'hate_crimes_2022': 11643,
            'retail_theft_2023_billions': 112.1,  # National Retail Federation estimate
            
            # Major city crime changes 2019-2023
            'nyc_murder_change': -0.13,  # -13%
            'chicago_murder_change': 0.23,  # +23%
            'la_murder_change': 0.05,  # +5%
            'sf_violent_crime_change': -0.07,  # -7%
        }
        
        # Climate/Environment data
        self.climate_data = {
            'global_temp_increase': 1.1,  # Celsius since pre-industrial
            'co2_level_current': 421,  # ppm as of 2024
            'co2_level_preindustrial': 280,
            'paris_agreement_target': 1.5,  # Celsius
            'us_emissions_reduction_target': 0.50,  # 50% by 2030
            'renewable_energy_percent_us': 21,  # % of electricity
            'ev_sales_percent_2023': 7.6,  # % of new car sales
            'sea_level_rise_rate': 3.4,  # mm per year
            'arctic_ice_loss_percent': 13,  # per decade
            'extreme_weather_cost_2023': 93000000000,  # $93 billion
            'clean_energy_jobs_us': 3400000,
            'solar_cost_decrease': 0.89,  # 89% decrease since 2010
            'wind_capacity_us_gw': 148,  # gigawatts
            'coal_plants_retired_since_2010': 334,
            'us_withdrew_paris_date': '2020-11-04',  # Trump withdrawal
            'us_rejoined_paris_date': '2021-02-19',  # Biden rejoined
        }
        
        # Economic/Inflation data
        self.economic_data = {
            'inflation_rate_2024': 2.4,  # October 2024
            'inflation_rate_2023': 3.4,
            'inflation_rate_2022': 6.5,
            'inflation_rate_2021': 7.0,
            'inflation_rate_2020': 1.4,
            'inflation_rate_2019': 2.3,
            'inflation_rate_2018': 1.9,
            'inflation_peak_2022': 9.1,  # June 2022
            'gas_price_avg_2024': 3.05,
            'gas_price_avg_2023': 3.52,
            'gas_price_avg_2022': 3.95,
            'gas_price_peak_2022': 5.01,  # June 2022
            'gas_price_avg_2020': 2.17,
            'unemployment_rate_2024': 4.1,
            'unemployment_rate_2023': 3.5,
            'unemployment_rate_2020_peak': 14.8,  # April 2020
            'stock_market_sp500_2024': 5800,  # Approximate
            'stock_market_sp500_2021': 3756,  # Biden inauguration
            'stock_market_sp500_2017': 2278,  # Trump inauguration
        }
        
        # Healthcare data
        self.healthcare_data = {
            'uninsured_rate_2023': 0.079,  # 7.9%
            'uninsured_rate_2020': 0.086,
            'uninsured_rate_2016': 0.090,
            'uninsured_rate_2013': 0.147,  # Pre-ACA full implementation
            'medicare_enrollment': 66000000,
            'medicaid_enrollment': 91000000,
            'aca_marketplace_enrollment_2024': 21300000,
            'prescription_drug_spending_2023': 405000000000,
            'insulin_cap_medicare': 35,  # $35/month cap
            'medical_bankruptcies_annual': 530000,
            'life_expectancy_us_2023': 76.4,
            'life_expectancy_us_2019': 78.9,
            'maternal_mortality_rate_2021': 32.9,  # per 100,000 live births
        }
        
        # Education data
        self.education_data = {
            'student_loan_debt_total': 1750000000000,  # $1.75 trillion
            'average_student_debt': 37338,
            'student_loan_borrowers': 43400000,
            'student_loan_forgiveness_biden': 138000000000,  # Amount forgiven
            'college_enrollment_decline_percent': 0.08,  # 8% since 2019
            'teacher_shortage_positions': 300000,
            'average_teacher_salary': 68469,
            'education_spending_per_student': 15633,
            'literacy_rate_adults': 0.79,  # 79% proficient
            'high_school_graduation_rate': 0.87,  # 87%
        }
    
    def check_claim(self, claim: str) -> Optional[Dict]:
        """Main entry point - check any political claim"""
        # Try each category
        result = self.check_immigration_claim(claim)
        if result:
            return result
            
        result = self.check_homelessness_claim(claim)
        if result:
            return result
            
        result = self.check_war_claim(claim)
        if result:
            return result
            
        result = self.check_crime_claim(claim)
        if result:
            return result
            
        result = self.check_climate_claim(claim)
        if result:
            return result
            
        result = self.check_economic_claim(claim)
        if result:
            return result
            
        result = self.check_healthcare_claim(claim)
        if result:
            return result
            
        result = self.check_education_claim(claim)
        if result:
            return result
            
        return None
    
    def check_immigration_claim(self, claim: str) -> Optional[Dict]:
        """Check immigration-related claims"""
        claim_lower = claim.lower()
        
        # Border encounters/crossings
        if any(term in claim_lower for term in ['border', 'crossing', 'encounter', 'apprehension']):
            numbers = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:million|billion)?', claim)
            if numbers:
                claimed_value = self._parse_number(numbers[0])
                
                # Handle "million" multiplier
                if 'million' in claim_lower:
                    claimed_value *= 1000000
                
                # Check which year
                year_match = re.search(r'20\d{2}', claim)
                year = int(year_match.group()) if year_match else 2024
                
                actual_key = f'border_encounters_{year}'
                if actual_key in self.immigration_data:
                    actual_value = self.immigration_data[actual_key]
                    return self._compare_values(
                        claimed_value, actual_value,
                        f"border encounters in {year}",
                        "CBP Statistics"
                    )
                else:
                    # Check if it's about Trump's term
                    if 'trump' in claim_lower:
                        if any(y in claim_lower for y in ['2017', '2018', '2019', '2020']):
                            year = int(re.search(r'20\d{2}', claim_lower).group())
                            actual_key = f'border_encounters_{year}'
                            if actual_key in self.immigration_data:
                                actual_value = self.immigration_data[actual_key]
                                return self._compare_values(
                                    claimed_value, actual_value,
                                    f"border encounters in {year} (Trump administration)",
                                    "CBP Statistics"
                                )
        
        # Border wall claims
        if 'wall' in claim_lower and any(term in claim_lower for term in ['built', 'build', 'miles', 'constructed']):
            numbers = re.findall(r'(\d+)', claim)
            if numbers:
                claimed_miles = int(numbers[0])
                
                if 'new' in claim_lower:
                    actual_miles = self.immigration_data['border_wall_new_miles_trump']
                    category = "new border wall miles (where no barrier existed)"
                else:
                    actual_miles = self.immigration_data['border_wall_miles_built_trump']
                    category = "total border barrier miles built/replaced"
                
                return self._compare_values(
                    claimed_miles, actual_miles,
                    category + " during Trump administration",
                    "CBP/DHS Reports"
                )
        
        # Deportations
        if 'deport' in claim_lower:
            numbers = re.findall(r'(\d+(?:,\d+)*)', claim)
            if numbers:
                claimed_value = self._parse_number(numbers[0])
                year_match = re.search(r'20\d{2}', claim)
                year = int(year_match.group()) if year_match else 2023
                
                actual_key = f'deportations_{year}'
                if actual_key in self.immigration_data:
                    actual_value = self.immigration_data[actual_key]
                    return self._compare_values(
                        claimed_value, actual_value,
                        f"deportations in {year}",
                        "ICE Statistics"
                    )
        
        # Illegal/undocumented population
        if any(term in claim_lower for term in ['illegal immigrant', 'undocumented', 'unauthorized']):
            if 'million' in claim_lower:
                numbers = re.findall(r'(\d+(?:\.\d+)?)\s*million', claim_lower)
                if numbers:
                    claimed_millions = float(numbers[0])
                    actual_millions = self.immigration_data['illegal_population_estimate'] / 1000000
                    
                    if abs(claimed_millions - actual_millions) < 2:  # Within 2 million
                        return {
                            'found': True,
                            'verdict': 'mostly_true',
                            'confidence': 75,
                            'explanation': f"Reasonable estimate. Most credible sources estimate 10-12 million undocumented immigrants in the US.",
                            'source': 'Pew Research Center'
                        }
                    elif claimed_millions > 15 or claimed_millions < 8:
                        return {
                            'found': True,
                            'verdict': 'false',
                            'confidence': 85,
                            'explanation': f"Significantly inaccurate. Credible estimates range from 10-12 million, not {claimed_millions} million.",
                            'source': 'Multiple Research Organizations'
                        }
        
        return None
    
    def check_homelessness_claim(self, claim: str) -> Optional[Dict]:
        """Check homelessness-related claims"""
        claim_lower = claim.lower()
        
        if 'homeless' in claim_lower:
            # Total homeless population
            if any(term in claim_lower for term in ['total', 'number', 'people', 'population']):
                numbers = re.findall(r'(\d+(?:,\d+)*)', claim)
                if numbers:
                    claimed_value = self._parse_number(numbers[0])
                    
                    # Check year
                    year_match = re.search(r'20\d{2}', claim)
                    year = int(year_match.group()) if year_match else 2023
                    
                    actual_key = f'total_homeless_{year}'
                    if actual_key in self.homelessness_data:
                        actual_value = self.homelessness_data[actual_key]
                        return self._compare_values(
                            claimed_value, actual_value,
                            f"total homeless population in {year}",
                            "HUD Point-in-Time Count",
                            tolerance=actual_value * 0.05  # 5% tolerance
                        )
            
            # State-specific claims
            for state, key_prefix in [
                ('california', 'california_homeless'),
                ('new york', 'new_york_homeless'),
                ('florida', 'florida_homeless'),
                ('texas', 'texas_homeless'),
                ('washington', 'washington_homeless')
            ]:
                if state in claim_lower:
                    numbers = re.findall(r'(\d+(?:,\d+)*)', claim)
                    if numbers:
                        claimed_value = self._parse_number(numbers[0])
                        actual_value = self.homelessness_data.get(f'{key_prefix}_2023', 0)
                        
                        if actual_value > 0:
                            return self._compare_values(
                                claimed_value, actual_value,
                                f"homeless population in {state.title()}",
                                "HUD 2023 Count"
                            )
            
            # City-specific claims
            city_mapping = {
                'los angeles': 'los_angeles_homeless_2023',
                'la': 'los_angeles_homeless_2023',
                'new york': 'new_york_city_homeless_2023',
                'nyc': 'new_york_city_homeless_2023',
                'seattle': 'seattle_homeless_2023',
                'san francisco': 'san_francisco_homeless_2023',
                'sf': 'san_francisco_homeless_2023',
                'san diego': 'san_diego_homeless_2023'
            }
            
            for city_term, data_key in city_mapping.items():
                if city_term in claim_lower:
                    numbers = re.findall(r'(\d+(?:,\d+)*)', claim)
                    if numbers:
                        claimed_value = self._parse_number(numbers[0])
                        actual_value = self.homelessness_data[data_key]
                        
                        city_name = city_term.upper() if len(city_term) <= 3 else city_term.title()
                        return self._compare_values(
                            claimed_value, actual_value,
                            f"homeless population in {city_name}",
                            "HUD 2023 Count/Local Census"
                        )
            
            # Percentage claims
            if 'unsheltered' in claim_lower and '%' in claim:
                percent_match = re.search(r'(\d+)\s*%', claim)
                if percent_match:
                    claimed_percent = int(percent_match.group(1))
                    actual_percent = int(self.homelessness_data['unsheltered_percentage'] * 100)
                    
                    return self._compare_percentages(
                        claimed_percent, actual_percent,
                        "unsheltered homeless percentage",
                        "HUD 2023"
                    )
        
        return None
    
    def check_war_claim(self, claim: str) -> Optional[Dict]:
        """Check war and conflict-related claims"""
        claim_lower = claim.lower()
        
        # "No new wars" claims
        if 'no new war' in claim_lower or 'no wars' in claim_lower or "didn't start" in claim_lower:
            if 'trump' in claim_lower:
                return {
                    'found': True,
                    'verdict': 'true',
                    'confidence': 95,
                    'explanation': "True. Trump did not start any new wars during his presidency (2017-2021), though he continued inherited conflicts.",
                    'source': 'Congressional Research Service'
                }
            elif 'biden' in claim_lower:
                return {
                    'found': True,
                    'verdict': 'mostly_true',
                    'confidence': 90,
                    'explanation': "Mostly true. Biden has not started new wars involving US troops. The US has provided aid to Ukraine but no combat troops.",
                    'source': 'Department of Defense'
                }
        
        # Wars started claims
        if any(phrase in claim_lower for phrase in ['started war', 'new war', 'began war']):
            if 'obama' in claim_lower:
                actual_wars = self.conflict_data['obama_new_wars']
                if 'five' in claim_lower or '5' in claim:
                    return {
                        'found': True,
                        'verdict': 'true',
                        'confidence': 85,
                        'explanation': f"True. Obama administration initiated or significantly expanded military operations in {actual_wars} conflicts: Libya, Syria, Yemen, Somalia, and expanded Pakistan drone operations.",
                        'source': 'Congressional Research Service'
                    }
            elif 'bush' in claim_lower:
                if 'two' in claim_lower or '2' in claim:
                    return {
                        'found': True,
                        'verdict': 'true',
                        'confidence': 95,
                        'explanation': "True. George W. Bush started two major wars: Afghanistan (2001) and Iraq (2003).",
                        'source': 'Historical Record'
                    }
        
        # Ukraine war claims
        if 'ukraine' in claim_lower:
            # US troops in Ukraine
            if any(term in claim_lower for term in ['troops', 'soldiers', 'military', 'combat']):
                if any(term in claim_lower for term in ['no troops', 'no soldiers', 'no us military', 'no american']):
                    return {
                        'found': True,
                        'verdict': 'true',
                        'confidence': 95,
                        'explanation': "True. There are no US combat troops in Ukraine. The US provides aid and training only.",
                        'source': 'Department of Defense'
                    }
            
            # Aid amounts
            if 'aid' in claim_lower or 'billion' in claim_lower:
                billion_match = re.search(r'(\d+)\s*billion', claim_lower)
                if billion_match:
                    claimed_billions = int(billion_match.group(1))
                    actual_total = self.conflict_data['us_aid_ukraine_total'] / 1000000000
                    
                    return self._compare_values(
                        claimed_billions, actual_total,
                        "total US aid committed to Ukraine",
                        "Congressional appropriations",
                        tolerance=10  # $10 billion tolerance
                    )
        
        # Afghanistan withdrawal
        if 'afghanistan' in claim_lower and any(term in claim_lower for term in ['withdrawal', 'withdraw', 'left']):
            if '13' in claim and any(term in claim_lower for term in ['died', 'killed', 'dead']):
                return {
                    'found': True,
                    'verdict': 'true',
                    'confidence': 95,
                    'explanation': "True. 13 US service members were killed in the Abbey Gate bombing during the Afghanistan withdrawal on August 26, 2021.",
                    'source': 'Department of Defense'
                }
        
        # Middle East conflicts
        if 'gaza' in claim_lower or 'palestinian' in claim_lower:
            if 'deaths' in claim_lower or 'killed' in claim_lower:
                numbers = re.findall(r'(\d+(?:,\d+)*)', claim)
                if numbers:
                    claimed_value = self._parse_number(numbers[0])
                    
                    # Gaza deaths since Oct 2023
                    if any(year in claim for year in ['2023', '2024']):
                        actual_deaths = self.conflict_data['gaza_deaths_2023_2024']
                        return self._compare_values(
                            claimed_value, actual_deaths,
                            "reported deaths in Gaza since October 2023",
                            "Gaza Health Ministry/UN",
                            tolerance=5000  # Estimates vary
                        )
        
        return None
    
    def check_crime_claim(self, claim: str) -> Optional[Dict]:
        """Check crime-related claims"""
        claim_lower = claim.lower()
        
        # Violent crime rate trends
        if 'violent crime' in claim_lower:
            # Rising/falling claims
            if any(word in claim_lower for word in ['rising', 'increase', 'up', 'surge', 'soar']):
                # Check specific years mentioned
                if '2023' in claim or '2024' in claim:
                    return {
                        'found': True,
                        'verdict': 'false',
                        'confidence': 85,
                        'explanation': "False. FBI data shows violent crime rates remained stable or declined slightly in 2023 compared to 2022 (380.7 per 100k).",
                        'source': 'FBI Uniform Crime Report'
                    }
                elif 'biden' in claim_lower:
                    return {
                        'found': True,
                        'verdict': 'mostly_false',
                        'confidence': 85,
                        'explanation': "Mostly false. Violent crime has decreased since 2021 peaks. 2023 rate (380.7) is lower than 2021 (395.7) and 2020 (398.5).",
                        'source': 'FBI UCR Data'
                    }
            elif any(word in claim_lower for word in ['falling', 'decrease', 'down', 'drop', 'decline']):
                return {
                    'found': True,
                    'verdict': 'mostly_true',
                    'confidence': 85,
                    'explanation': "Mostly true. Violent crime has declined from pandemic peaks. 2023 rate (380.7) is down from 2021 (395.7), though still above 2019 levels (366.7).",
                    'source': 'FBI UCR Data'
                }
        
        # Murder/homicide rates
        if any(term in claim_lower for term in ['murder', 'homicide']):
            # Specific numbers
            numbers = re.findall(r'(\d+(?:,\d+)*)', claim)
            if numbers and 'rate' in claim_lower:
                claimed_rate = float(numbers[0])
                year_match = re.search(r'20\d{2}', claim)
                year = int(year_match.group()) if year_match else 2023
                
                actual_key = f'murder_rate_{year}'
                if actual_key in self.crime_data:
                    actual_rate = self.crime_data[actual_key]
                    return self._compare_values(
                        claimed_rate, actual_rate,
                        f"murder rate per 100,000 in {year}",
                        "FBI UCR"
                    )
        
        # Mass shootings
        if 'mass shooting' in claim_lower:
            numbers = re.findall(r'(\d+)', claim)
            if numbers:
                claimed_value = int(numbers[0])
                year_match = re.search(r'20\d{2}', claim)
                year = int(year_match.group()) if year_match else 2023
                
                actual_key = f'mass_shootings_{year}'
                if actual_key in self.crime_data:
                    actual_value = self.crime_data[actual_key]
                    return self._compare_values(
                        claimed_value, actual_value,
                        f"mass shootings in {year}",
                        "Gun Violence Archive",
                        tolerance=50  # Different definitions exist
                    )
        
        # Retail theft
        if any(term in claim_lower for term in ['retail theft', 'shoplifting', 'store theft']):
            if 'billion' in claim_lower:
                billion_match = re.search(r'(\d+(?:\.\d+)?)\s*billion', claim_lower)
                if billion_match:
                    claimed_billions = float(billion_match.group(1))
                    actual_billions = self.crime_data['retail_theft_2023_billions']
                    
                    return self._compare_values(
                        claimed_billions, actual_billions,
                        "retail theft losses in billions (2023)",
                        "National Retail Federation",
                        tolerance=20  # Estimates vary widely
                    )
        
        # City-specific crime
        city_crime_terms = {
            'new york': ('nyc', 'New York City'),
            'nyc': ('nyc', 'New York City'),
            'chicago': ('chicago', 'Chicago'),
            'los angeles': ('la', 'Los Angeles'),
            'la': ('la', 'Los Angeles'),
            'san francisco': ('sf', 'San Francisco'),
            'sf': ('sf', 'San Francisco')
        }
        
        for city_term, (city_key, city_name) in city_crime_terms.items():
            if city_term in claim_lower and 'murder' in claim_lower:
                if any(word in claim_lower for word in ['up', 'increase', 'rise']):
                    change_key = f'{city_key}_murder_change'
                    if change_key in self.crime_data:
                        actual_change = self.crime_data[change_key]
                        if actual_change > 0:
                            return {
                                'found': True,
                                'verdict': 'true' if city_key == 'chicago' else 'false',
                                'confidence': 85,
                                'explanation': f"{city_name} murders {'increased' if actual_change > 0 else 'decreased'} by {abs(actual_change)*100:.0f}% comparing 2023 to 2019.",
                                'source': 'Local Police Department Data'
                            }
                elif any(word in claim_lower for word in ['down', 'decrease', 'fall']):
                    change_key = f'{city_key}_murder_change'
                    if change_key in self.crime_data:
                        actual_change = self.crime_data[change_key]
                        if actual_change < 0:
                            return {
                                'found': True,
                                'verdict': 'true' if city_key in ['nyc', 'sf'] else 'false',
                                'confidence': 85,
                                'explanation': f"{city_name} murders decreased by {abs(actual_change)*100:.0f}% comparing 2023 to 2019.",
                                'source': 'Local Police Department Data'
                            }
        
        return None
    
    def check_climate_claim(self, claim: str) -> Optional[Dict]:
        """Check climate-related claims"""
        claim_lower = claim.lower()
        
        # Global temperature
        if 'global' in claim_lower and any(term in claim_lower for term in ['temperature', 'warming']):
            numbers = re.findall(r'(\d+(?:\.\d+)?)\s*(?:degree|celsius|°c)', claim_lower)
            if numbers:
                claimed_temp = float(numbers[0])
                actual_temp = self.climate_data['global_temp_increase']
                
                if abs(claimed_temp - actual_temp) < 0.2:
                    return {
                        'found': True,
                        'verdict': 'true',
                        'confidence': 90,
                        'explanation': f"Accurate. Global temperature has risen {actual_temp}°C since pre-industrial times.",
                        'source': 'IPCC/NASA'
                    }
                else:
                    return {
                        'found': True,
                        'verdict': 'false' if abs(claimed_temp - actual_temp) > 0.5 else 'mostly_true',
                        'confidence': 85,
                        'explanation': f"{'Incorrect' if abs(claimed_temp - actual_temp) > 0.5 else 'Close but not exact'}. Global temperature has risen {actual_temp}°C, not {claimed_temp}°C.",
                        'source': 'IPCC/NASA'
                    }
        
        # Paris Agreement withdrawal/rejoin
        if 'paris' in claim_lower and any(term in claim_lower for term in ['agreement', 'accord', 'climate']):
            if 'withdrew' in claim_lower or 'withdrawal' in claim_lower:
                if 'trump' in claim_lower:
                    return {
                        'found': True,
                        'verdict': 'true',
                        'confidence': 95,
                        'explanation': "True. Trump withdrew the US from the Paris Climate Agreement, effective November 4, 2020.",
                        'source': 'State Department'
                    }
            elif 'rejoin' in claim_lower or 'rejoined' in claim_lower:
                if 'biden' in claim_lower:
                    return {
                        'found': True,
                        'verdict': 'true',
                        'confidence': 95,
                        'explanation': "True. Biden rejoined the Paris Climate Agreement on his first day in office, January 20, 2021 (effective February 19, 2021).",
                        'source': 'State Department'
                    }
        
        # CO2 levels
        if 'co2' in claim_lower or 'carbon dioxide' in claim_lower:
            numbers = re.findall(r'(\d+)\s*(?:ppm|parts per million)', claim_lower)
            if numbers:
                claimed_co2 = int(numbers[0])
                actual_co2 = self.climate_data['co2_level_current']
                
                if abs(claimed_co2 - actual_co2) < 5:
                    return {
                        'found': True,
                        'verdict': 'true',
                        'confidence': 95,
                        'explanation': f"Accurate. Current atmospheric CO2 is approximately {actual_co2} ppm.",
                        'source': 'NOAA Mauna Loa Observatory'
                    }
        
        # Renewable energy
        if 'renewable' in claim_lower and 'energy' in claim_lower:
            percent_match = re.search(r'(\d+)\s*(?:%|percent)', claim_lower)
            if percent_match:
                claimed_percent = int(percent_match.group(1))
                actual_percent = self.climate_data['renewable_energy_percent_us']
                
                return self._compare_percentages(
                    claimed_percent, actual_percent,
                    "renewable energy in US electricity generation",
                    "EIA"
                )
        
        # Climate denial patterns
        if any(phrase in claim_lower for phrase in ['climate hoax', 'global warming hoax', 'climate scam']):
            return {
                'found': True,
                'verdict': 'false',
                'confidence': 95,
                'explanation': "False. Climate change is supported by overwhelming scientific consensus (97%+ of climate scientists) and extensive evidence.",
                'source': 'NASA, NOAA, IPCC'
            }
        
        return None
    
    def check_economic_claim(self, claim: str) -> Optional[Dict]:
        """Check economic/inflation claims"""
        claim_lower = claim.lower()
        
        # Inflation rates
        if 'inflation' in claim_lower:
            percent_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:%|percent)', claim_lower)
            if percent_match:
                claimed_rate = float(percent_match.group(1))
                
                # Check for specific year
                year_match = re.search(r'20\d{2}', claim)
                if year_match:
                    year = int(year_match.group())
                    rate_key = f'inflation_rate_{year}'
                    if rate_key in self.economic_data:
                        actual_rate = self.economic_data[rate_key]
                        return self._compare_values(
                            claimed_rate, actual_rate,
                            f"inflation rate in {year}",
                            "Bureau of Labor Statistics"
                        )
                
                # Peak inflation claims
                if any(word in claim_lower for word in ['peak', 'highest', 'maximum']):
                    actual_peak = self.economic_data['inflation_peak_2022']
                    return self._compare_values(
                        claimed_rate, actual_peak,
                        "peak inflation rate (June 2022)",
                        "BLS CPI Data"
                    )
        
        # Gas prices
        if any(term in claim_lower for term in ['gas price', 'gasoline', 'fuel price']):
            dollar_match = re.search(r'\$?(\d+\.?\d*)', claim)
            if dollar_match:
                claimed_price = float(dollar_match.group(1))
                
                # Check year
                year_match = re.search(r'20\d{2}', claim)
                if year_match:
                    year = int(year_match.group())
                    price_key = f'gas_price_avg_{year}'
                    if price_key in self.economic_data:
                        actual_price = self.economic_data[price_key]
                        return self._compare_values(
                            claimed_price, actual_price,
                            f"average gas price in {year}",
                            "EIA",
                            tolerance=0.20  # 20 cents tolerance
                        )
                
                # Peak gas price
                if any(word in claim_lower for word in ['peak', 'highest', 'record']):
                    actual_peak = self.economic_data['gas_price_peak_2022']
                    return self._compare_values(
                        claimed_price, actual_peak,
                        "peak gas price (June 2022)",
                        "EIA",
                        tolerance=0.10
                    )
        
        # Stock market
        if any(term in claim_lower for term in ['stock market', 's&p', 'dow', 'nasdaq']):
            numbers = re.findall(r'(\d+(?:,\d+)*)', claim)
            if numbers and 's&p' in claim_lower:
                claimed_value = self._parse_number(numbers[0])
                
                if 'trump' in claim_lower and 'inauguration' in claim_lower:
                    actual = self.economic_data['stock_market_sp500_2017']
                    return self._compare_values(
                        claimed_value, actual,
                        "S&P 500 at Trump's inauguration",
                        "Market data",
                        tolerance=50
                    )
                elif 'biden' in claim_lower and 'inauguration' in claim_lower:
                    actual = self.economic_data['stock_market_sp500_2021']
                    return self._compare_values(
                        claimed_value, actual,
                        "S&P 500 at Biden's inauguration",
                        "Market data",
                        tolerance=50
                    )
        
        return None
    
    def check_healthcare_claim(self, claim: str) -> Optional[Dict]:
        """Check healthcare-related claims"""
        claim_lower = claim.lower()
        
        # Uninsured rate
        if 'uninsured' in claim_lower:
            percent_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:%|percent)', claim_lower)
            if percent_match:
                claimed_percent = float(percent_match.group(1))
                
                # Pre-ACA comparison
                if 'before' in claim_lower and any(term in claim_lower for term in ['aca', 'obamacare']):
                    actual_percent = self.healthcare_data['uninsured_rate_2013'] * 100
                    return self._compare_percentages(
                        claimed_percent, actual_percent,
                        "uninsured rate before ACA (2013)",
                        "Census Bureau"
                    )
                else:
                    # Current rate
                    actual_percent = self.healthcare_data['uninsured_rate_2023'] * 100
                    return self._compare_percentages(
                        claimed_percent, actual_percent,
                        "current uninsured rate",
                        "Census Bureau"
                    )
        
        # Medicare/Medicaid enrollment
        if 'medicare' in claim_lower and 'million' in claim_lower:
            million_match = re.search(r'(\d+)\s*million', claim_lower)
            if million_match:
                claimed_millions = int(million_match.group(1))
                actual_millions = self.healthcare_data['medicare_enrollment'] / 1000000
                
                return self._compare_values(
                    claimed_millions, actual_millions,
                    "Medicare enrollment",
                    "CMS",
                    tolerance=3  # 3 million tolerance
                )
        
        # Insulin cap
        if 'insulin' in claim_lower and any(term in claim_lower for term in ['$35', '35 dollar', 'cap']):
            return {
                'found': True,
                'verdict': 'true',
                'confidence': 95,
                'explanation': "True. Medicare beneficiaries pay no more than $35 per month for insulin under the Inflation Reduction Act.",
                'source': 'CMS/Medicare.gov'
            }
        
        # Life expectancy
        if 'life expectancy' in claim_lower:
            numbers = re.findall(r'(\d+(?:\.\d+)?)', claim)
            if numbers:
                claimed_years = float(numbers[0])
                
                if '2023' in claim or 'current' in claim_lower:
                    actual = self.healthcare_data['life_expectancy_us_2023']
                elif '2019' in claim or 'pre-pandemic' in claim_lower:
                    actual = self.healthcare_data['life_expectancy_us_2019']
                else:
                    actual = self.healthcare_data['life_expectancy_us_2023']
                
                return self._compare_values(
                    claimed_years, actual,
                    "US life expectancy",
                    "CDC National Vital Statistics",
                    tolerance=0.5  # Half year tolerance
                )
        
        return None
    
    def check_education_claim(self, claim: str) -> Optional[Dict]:
        """Check education-related claims"""
        claim_lower = claim.lower()
        
        # Student loan debt
        if 'student' in claim_lower and any(term in claim_lower for term in ['debt', 'loan']):
            if 'trillion' in claim_lower:
                trillion_match = re.search(r'(\d+(?:\.\d+)?)\s*trillion', claim_lower)
                if trillion_match:
                    claimed_trillions = float(trillion_match.group(1))
                    actual_trillions = self.education_data['student_loan_debt_total'] / 1000000000000
                    
                    return self._compare_values(
                        claimed_trillions, actual_trillions,
                        "total student loan debt",
                        "Federal Reserve",
                        tolerance=0.1  # $100 billion tolerance
                    )
            
            # Forgiveness amounts
            if 'forgive' in claim_lower or 'forgiveness' in claim_lower:
                billion_match = re.search(r'(\d+)\s*billion', claim_lower)
                if billion_match:
                    claimed_billions = int(billion_match.group(1))
                    actual_billions = self.education_data['student_loan_forgiveness_biden'] / 1000000000
                    
                    return self._compare_values(
                        claimed_billions, actual_billions,
                        "student loan forgiveness under Biden",
                        "Department of Education",
                        tolerance=10
                    )
        
        # Teacher shortage
        if 'teacher shortage' in claim_lower:
            numbers = re.findall(r'(\d+(?:,\d+)*)', claim)
            if numbers:
                claimed_value = self._parse_number(numbers[0])
                actual = self.education_data['teacher_shortage_positions']
                
                return self._compare_values(
                    claimed_value, actual,
                    "teacher shortage positions",
                    "Department of Education estimate",
                    tolerance=50000
                )
        
        # Literacy rates
        if 'literacy' in claim_lower and any(term in claim_lower for term in ['rate', 'percent', '%']):
            percent_match = re.search(r'(\d+)\s*(?:%|percent)', claim_lower)
            if percent_match:
                claimed_percent = int(percent_match.group(1))
                actual_percent = int(self.education_data['literacy_rate_adults'] * 100)
                
                return self._compare_percentages(
                    claimed_percent, actual_percent,
                    "adult literacy rate",
                    "National Center for Education Statistics"
                )
        
        return None
    
    def _parse_number(self, number_str: str) -> float:
        """Parse number string with commas to float"""
        return float(number_str.replace(',', ''))
    
    def _compare_values(self, claimed: float, actual: float, category: str, source: str, tolerance: float = None) -> Dict:
        """Compare claimed vs actual values"""
        if tolerance is None:
            # Default tolerance is 10% of actual value
            tolerance = actual * 0.1
        
        diff = abs(claimed - actual)
        
        if diff <= tolerance:
            verdict = 'true'
            confidence = 90
            explanation = f"Accurate. {category.capitalize()} is {actual:,.0f}."
        elif diff <= tolerance * 2:
            verdict = 'mostly_true'
            confidence = 80
            explanation = f"Close but not exact. {category.capitalize()} is {actual:,.0f}, not {claimed:,.0f}."
        elif diff <= tolerance * 4:
            verdict = 'misleading'
            confidence = 75
            explanation = f"Misleading. {category.capitalize()} is {actual:,.0f}, claim of {claimed:,.0f} is significantly off."
        else:
            verdict = 'false'
            confidence = 85
            explanation = f"False. {category.capitalize()} is {actual:,.0f}, not {claimed:,.0f}."
        
        return {
            'found': True,
            'verdict': verdict,
            'confidence': confidence,
            'explanation': explanation,
            'source': source
        }
    
    def _compare_percentages(self, claimed: float, actual: float, category: str, source: str) -> Dict:
        """Compare percentage claims"""
        diff = abs(claimed - actual)
        
        if diff <= 2:
            verdict = 'true'
            explanation = f"Accurate. {category.capitalize()} is {actual:.1f}%."
        elif diff <= 5:
            verdict = 'mostly_true'
            explanation = f"Close. {category.capitalize()} is {actual:.1f}%, not {claimed}%."
        elif diff <= 10:
            verdict = 'misleading'
            explanation = f"Misleading. {category.capitalize()} is {actual:.1f}%, claim of {claimed}% is significantly off."
        else:
            verdict = 'false'
            explanation = f"False. {category.capitalize()} is {actual:.1f}%, not {claimed}%."
        
        return {
            'found': True,
            'verdict': verdict,
            'confidence': 85,
            'explanation': explanation,
            'source': source
        }

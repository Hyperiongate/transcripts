"""
Political Topics Fact Checking Module
Handles immigration, climate, Ukraine, tariffs, vaccines, and other political topics
"""
import re
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PoliticalTopicsChecker:
    """Check claims about common political topics"""
    
    def __init__(self):
        # Immigration statistics (2024 data)
        self.immigration_data = {
            'border_encounters_2024': 2475669,  # FY2024 through August
            'border_encounters_2023': 2475669,  # FY2023 total
            'border_encounters_2022': 2378944,
            'border_encounters_2021': 1734686,
            'border_encounters_2020': 458088,
            'border_encounters_2019': 977509,
            'deportations_2023': 142580,
            'deportations_2022': 72177,
            'deportations_2021': 59011,
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
            'green_cards_issued_2023': 1018349
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
            'coal_plants_retired_since_2010': 334
        }
        
        # Ukraine conflict data
        self.ukraine_data = {
            'us_aid_total_billions': 113,  # Total committed
            'military_aid_billions': 76.8,
            'humanitarian_aid_billions': 26.4,
            'economic_aid_billions': 9.8,
            'nato_members': 32,
            'ukraine_refugees': 6200000,
            'internally_displaced': 3700000,
            'war_start_date': '2022-02-24',
            'ukrainian_civilian_deaths_un': 10582,  # UN verified minimum
            'infrastructure_damage_billions': 150,
            'grain_export_deal_tons': 32900000,
            'sanctions_on_russia': 16500,  # Individual sanctions
            'russian_gdp_decline_2022': 0.021,  # 2.1%
        }
        
        # Trade/Tariff data
        self.trade_data = {
            'trade_deficit_2023_billions': 773,
            'trade_deficit_china_2023_billions': 279,
            'average_tariff_rate_us': 0.019,  # 1.9%
            'china_tariffs_trump': 0.25,  # 25% on many goods
            'china_tariffs_current': 0.25,  # Still in place
            'mexico_trade_volume_billions': 798,
            'canada_trade_volume_billions': 782,
            'usmca_jobs_created': 0,  # Disputed/unverified
            'manufacturing_jobs_us': 12900000,
            'farm_exports_2023_billions': 178,
            'steel_tariff_232': 0.25,  # 25%
            'aluminum_tariff_232': 0.10,  # 10%
            'wto_cases_us_involved': 625,
            'nafta_start_year': 1994,
            'usmca_start_year': 2020
        }
        
        # Vaccine/Health data
        self.vaccine_data = {
            'covid_vaccines_administered_us': 676000000,
            'covid_fully_vaccinated_percent': 69.5,
            'covid_booster_percent': 17.0,  # Latest booster
            'covid_deaths_us_total': 1170000,
            'vaccine_effectiveness_hospitalization': 0.90,  # 90%
            'childhood_vaccination_rate': 0.925,  # 92.5%
            'measles_cases_2023': 58,
            'flu_vaccine_effectiveness_2023': 0.48,  # 48%
            'vaccine_adverse_events_serious': 0.0001,  # 0.01%
            'polio_cases_us_2023': 0,
            'hpv_vaccination_rate': 0.589,  # 58.9%
            'autism_vaccine_link': False,  # Definitively disproven
            'mrna_vaccines_approved': 2,  # Pfizer, Moderna
            'vaccine_mandates_federal_employees': False,  # Ended May 2023
        }
        
        # Drug policy data  
        self.drug_data = {
            'overdose_deaths_2023': 107543,
            'overdose_deaths_2022': 109680,
            'fentanyl_deaths_2023': 74702,
            'marijuana_legal_states': 38,  # Medical
            'marijuana_recreational_states': 24,
            'federal_marijuana_schedule': 1,
            'marijuana_arrests_2022': 227108,
            'drug_war_cost_annual_billions': 51,
            'incarcerated_drug_offenses': 430926,
            'treatment_funding_billions': 42.5,
            'naloxone_saves_estimated': 150000,
            'prescription_monitoring_states': 50,
            'supervised_injection_sites_us': 2,
            'drug_courts_us': 4000
        }
        
        # Crime statistics
        self.crime_data = {
            'violent_crime_rate_2023': 380.7,  # per 100k
            'murder_rate_2023': 6.3,  # per 100k
            'property_crime_rate_2023': 1954.4,
            'police_officers_us': 708000,
            'prison_population': 1230000,
            'crime_clearance_rate': 0.456,  # 45.6%
            'gun_homicides_2023': 19350,
            'mass_shootings_2023': 656,
            'police_shootings_2023': 1163,
            'hate_crimes_2022': 11643,
            'juvenile_arrests_2022': 424300,
            'recidivism_rate_3year': 0.68,  # 68%
        }
    
    def check_immigration_claim(self, claim: str) -> Optional[Dict]:
        """Check immigration-related claims"""
        claim_lower = claim.lower()
        
        # Border encounters
        if 'border' in claim_lower and any(word in claim_lower for word in ['encounter', 'crossing', 'apprehension']):
            numbers = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:million|billion)?', claim)
            if numbers:
                claimed_value = self._parse_number(numbers[0])
                
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
        
        # DACA
        if 'daca' in claim_lower or 'dreamer' in claim_lower:
            numbers = re.findall(r'(\d+(?:,\d+)*)', claim)
            if numbers:
                claimed_value = self._parse_number(numbers[0])
                actual_value = self.immigration_data['daca_recipients']
                return self._compare_values(
                    claimed_value, actual_value,
                    "DACA recipients",
                    "USCIS Statistics"
                )
        
        return None
    
    def check_climate_claim(self, claim: str) -> Optional[Dict]:
        """Check climate-related claims"""
        claim_lower = claim.lower()
        
        # Global temperature
        if 'global' in claim_lower and 'temperature' in claim_lower:
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
    
    def check_ukraine_claim(self, claim: str) -> Optional[Dict]:
        """Check Ukraine conflict-related claims"""
        claim_lower = claim.lower()
        
        # US aid amounts
        if 'aid' in claim_lower and 'ukraine' in claim_lower:
            billion_match = re.search(r'(\d+)\s*billion', claim_lower)
            if billion_match:
                claimed_billions = int(billion_match.group(1))
                
                if 'military' in claim_lower:
                    actual = self.ukraine_data['military_aid_billions']
                    category = "military aid"
                elif 'humanitarian' in claim_lower:
                    actual = self.ukraine_data['humanitarian_aid_billions']
                    category = "humanitarian aid"
                else:
                    actual = self.ukraine_data['us_aid_total_billions']
                    category = "total aid"
                
                return self._compare_values(
                    claimed_billions, actual,
                    f"US {category} to Ukraine",
                    "State Department/DOD",
                    tolerance=5  # Within $5 billion
                )
        
        # Refugee numbers
        if 'refugee' in claim_lower and 'ukraine' in claim_lower:
            million_match = re.search(r'(\d+)\s*million', claim_lower)
            if million_match:
                claimed_millions = int(million_match.group(1))
                actual_millions = self.ukraine_data['ukraine_refugees'] / 1000000
                
                return self._compare_values(
                    claimed_millions, actual_millions,
                    "Ukrainian refugees",
                    "UNHCR",
                    tolerance=0.5
                )
        
        return None
    
    def check_vaccine_claim(self, claim: str) -> Optional[Dict]:
        """Check vaccine-related claims"""
        claim_lower = claim.lower()
        
        # Autism link (high priority debunking)
        if 'vaccine' in claim_lower and 'autism' in claim_lower:
            if any(word in claim_lower for word in ['cause', 'link', 'connect', 'lead']):
                return {
                    'found': True,
                    'verdict': 'false',
                    'confidence': 99,
                    'explanation': "Definitively false. Multiple large-scale studies involving millions of children have found no link between vaccines and autism. The original study claiming this was retracted for fraud.",
                    'source': 'CDC, WHO, dozens of peer-reviewed studies'
                }
        
        # COVID vaccination rates
        if 'covid' in claim_lower and 'vaccin' in claim_lower:
            percent_match = re.search(r'(\d+)\s*(?:%|percent)', claim_lower)
            if percent_match:
                claimed_percent = int(percent_match.group(1))
                
                if 'fully' in claim_lower:
                    actual = self.vaccine_data['covid_fully_vaccinated_percent']
                    category = "fully vaccinated Americans"
                elif 'booster' in claim_lower:
                    actual = self.vaccine_data['covid_booster_percent']
                    category = "Americans with latest booster"
                else:
                    actual = self.vaccine_data['covid_fully_vaccinated_percent']
                    category = "vaccinated Americans"
                
                return self._compare_percentages(
                    claimed_percent, actual,
                    category,
                    "CDC"
                )
        
        # Vaccine effectiveness
        if 'effective' in claim_lower and 'vaccine' in claim_lower:
            percent_match = re.search(r'(\d+)\s*(?:%|percent)', claim_lower)
            if percent_match:
                claimed_percent = int(percent_match.group(1))
                
                if 'hospital' in claim_lower:
                    actual_percent = int(self.vaccine_data['vaccine_effectiveness_hospitalization'] * 100)
                    return self._compare_percentages(
                        claimed_percent, actual_percent,
                        "COVID vaccine effectiveness against hospitalization",
                        "CDC studies"
                    )
        
        return None
    
    def check_drug_claim(self, claim: str) -> Optional[Dict]:
        """Check drug policy-related claims"""
        claim_lower = claim.lower()
        
        # Overdose deaths
        if 'overdose' in claim_lower:
            numbers = re.findall(r'(\d+(?:,\d+)*)', claim)
            if numbers:
                claimed_value = self._parse_number(numbers[0])
                
                if 'fentanyl' in claim_lower:
                    actual = self.drug_data['fentanyl_deaths_2023']
                    category = "fentanyl overdose deaths (2023)"
                else:
                    actual = self.drug_data['overdose_deaths_2023']
                    category = "total overdose deaths (2023)"
                
                return self._compare_values(
                    claimed_value, actual,
                    category,
                    "CDC WONDER Database"
                )
        
        # Marijuana legalization
        if 'marijuana' in claim_lower or 'cannabis' in claim_lower:
            if 'legal' in claim_lower and 'states' in claim_lower:
                numbers = re.findall(r'(\d+)\s*state', claim_lower)
                if numbers:
                    claimed_states = int(numbers[0])
                    
                    if 'recreational' in claim_lower:
                        actual = self.drug_data['marijuana_recreational_states']
                        category = "states with recreational marijuana"
                    else:
                        actual = self.drug_data['marijuana_legal_states']
                        category = "states with medical marijuana"
                    
                    return self._compare_values(
                        claimed_states, actual,
                        category,
                        "NORML/State databases",
                        tolerance=2  # States change frequently
                    )
        
        return None
    
    def check_trade_claim(self, claim: str) -> Optional[Dict]:
        """Check trade/tariff-related claims"""
        claim_lower = claim.lower()
        
        # Trade deficit
        if 'trade deficit' in claim_lower:
            billion_match = re.search(r'(\d+)\s*billion', claim_lower)
            if billion_match:
                claimed_billions = int(billion_match.group(1))
                
                if 'china' in claim_lower:
                    actual = self.trade_data['trade_deficit_china_2023_billions']
                    category = "trade deficit with China (2023)"
                else:
                    actual = self.trade_data['trade_deficit_2023_billions']
                    category = "total US trade deficit (2023)"
                
                return self._compare_values(
                    claimed_billions, actual,
                    category,
                    "US Census Bureau",
                    tolerance=20  # $20 billion tolerance
                )
        
        # Tariff rates
        if 'tariff' in claim_lower:
            percent_match = re.search(r'(\d+)\s*(?:%|percent)', claim_lower)
            if percent_match:
                claimed_percent = int(percent_match.group(1))
                
                if 'china' in claim_lower:
                    actual_percent = int(self.trade_data['china_tariffs_current'] * 100)
                    return {
                        'found': True,
                        'verdict': 'true' if claimed_percent == actual_percent else 'mostly_true',
                        'confidence': 90,
                        'explanation': f"Trump-era tariffs of {actual_percent}% on many Chinese goods remain in place under Biden.",
                        'source': 'USTR'
                    }
        
        return None
    
    def check_crime_claim(self, claim: str) -> Optional[Dict]:
        """Check crime-related claims"""
        claim_lower = claim.lower()
        
        # Crime rates
        if 'crime rate' in claim_lower:
            if 'violent' in claim_lower:
                # Check if claim says rising/falling
                if any(word in claim_lower for word in ['rising', 'increase', 'up', 'surge']):
                    return {
                        'found': True,
                        'verdict': 'false',
                        'confidence': 85,
                        'explanation': "False. Violent crime rates have generally declined from 2020-2023 peaks, though remain above 2019 levels.",
                        'source': 'FBI Crime Data'
                    }
                elif any(word in claim_lower for word in ['falling', 'decrease', 'down', 'drop']):
                    return {
                        'found': True,
                        'verdict': 'mostly_true',
                        'confidence': 85,
                        'explanation': "Mostly true. Violent crime has declined since 2020-2021 peaks but remains elevated compared to pre-2020.",
                        'source': 'FBI Crime Data'
                    }
        
        # Specific crime statistics
        numbers = re.findall(r'(\d+(?:,\d+)*)', claim)
        if numbers and any(crime in claim_lower for crime in ['murder', 'homicide', 'shooting']):
            claimed_value = self._parse_number(numbers[0])
            
            if 'mass shooting' in claim_lower:
                actual = self.crime_data['mass_shootings_2023']
                return self._compare_values(
                    claimed_value, actual,
                    "mass shootings in 2023",
                    "Gun Violence Archive",
                    tolerance=50  # Different definitions exist
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
    
    def _compare_percentages(self, claimed: int, actual: float, category: str, source: str) -> Dict:
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

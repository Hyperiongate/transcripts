"""
Context Resolution Module - Enhanced with Full Transcript Analysis
Handles pronoun resolution and contextual understanding
"""
import re
from typing import List, Tuple, Dict, Optional, Set
from collections import defaultdict

class ContextResolver:
    """Resolve contextual references in claims using full transcript context"""
    
    def __init__(self):
        self.previous_claims = []
        self.max_context_size = 10
        self.entities = defaultdict(list)  # entity type -> list of entities
        self.name_map = {}  # first name -> full name
        self.title_map = {}  # title -> person
        self.full_transcript = ""
        
    def analyze_full_transcript(self, transcript: str):
        """Analyze the full transcript to extract all entities and build context"""
        self.full_transcript = transcript
        
        # Extract all named entities
        self._extract_all_entities(transcript)
        
        # Build name mappings
        self._build_name_mappings()
        
        # Extract topics and themes
        self._extract_topics(transcript)
    
    def _extract_all_entities(self, transcript: str):
        """Extract all named entities from the transcript"""
        # Reset entities
        self.entities.clear()
        
        # Pattern for full names (First Last)
        full_name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'
        full_names = re.findall(full_name_pattern, transcript)
        
        for name in full_names:
            parts = name.split()
            if len(parts) >= 2:
                self.entities['people'].append(name)
                # Map first name to full name
                first_name = parts[0]
                if first_name not in self.name_map:
                    self.name_map[first_name] = []
                if name not in self.name_map[first_name]:
                    self.name_map[first_name].append(name)
        
        # Pattern for titles + names
        title_pattern = r'\b(Mr\.|Ms\.|Dr\.|President|Senator|Representative|Governor|Mayor|CEO|Director|Professor|Judge)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        title_matches = re.findall(title_pattern, transcript)
        
        for title, name in title_matches:
            full_ref = f"{title} {name}"
            self.entities['people'].append(full_ref)
            self.title_map[title] = name
            
            # Also map the name without title
            if name not in self.entities['people']:
                self.entities['people'].append(name)
            
            # Update first name mapping
            first_name = name.split()[0]
            if first_name not in self.name_map:
                self.name_map[first_name] = []
            if name not in self.name_map[first_name]:
                self.name_map[first_name].append(name)
        
        # Extract organizations
        org_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Inc|Corp|LLC|Ltd|Company|Corporation|Foundation|Institute|University|College|School|Hospital|Center|Agency|Department|Committee|Commission|Bureau|Office))\b'
        orgs = re.findall(org_pattern, transcript)
        self.entities['organizations'].extend(orgs)
        
        # Extract locations
        location_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,?\s+(?:Street|Avenue|Road|Boulevard|City|State|County))\b'
        locations = re.findall(location_pattern, transcript)
        self.entities['locations'].extend(locations)
        
        # Extract common places
        places_pattern = r'\b(New York|Los Angeles|Chicago|Houston|Phoenix|Philadelphia|San Antonio|San Diego|Dallas|San Jose|Austin|Jacksonville|Fort Worth|Columbus|San Francisco|Charlotte|Indianapolis|Seattle|Denver|Washington|Boston|El Paso|Detroit|Nashville|Portland|Memphis|Oklahoma City|Las Vegas|Louisville|Baltimore|Milwaukee|Albuquerque|Tucson|Fresno|Mesa|Sacramento|Atlanta|Kansas City|Colorado Springs|Miami|Raleigh|Omaha|Long Beach|Virginia Beach|Oakland|Minneapolis|Tulsa|Arlington|Tampa|New Orleans|Wichita|Cleveland|Bakersfield|Aurora|Anaheim|Honolulu|Santa Ana|Riverside|Corpus Christi|Lexington|Stockton|Henderson|Saint Paul|St\. Louis|Cincinnati|Pittsburgh|Greensboro|Anchorage|Plano|Lincoln|Orlando|Irvine|Newark|Toledo|Durham|Chula Vista|Fort Wayne|Jersey City|St\. Petersburg|Laredo|Madison|Chandler|Buffalo|Lubbock|Scottsdale|Reno|Glendale|Gilbert|Winston-Salem|North Las Vegas|Norfolk|Chesapeake|Garland|Irving|Hialeah|Fremont|Boise|Richmond|Baton Rouge|Spokane|Des Moines|Tacoma|San Bernardino|Modesto|Fontana|Santa Clarita|Birmingham|Oxnard|Fayetteville|Moreno Valley|Rochester|Glendale|Huntington Beach|Salt Lake City|Grand Rapids|Amarillo|Yonkers|Aurora|Montgomery|Akron|Little Rock|Huntsville|Augusta|Port St\. Lucie|Grand Prairie|Columbus|Tallahassee|Overland Park|Tempe|McKinney|Mobile|Cape Coral|Shreveport|Frisco|Knoxville|Worcester|Brownsville|Vancouver|Fort Lauderdale|Sioux Falls|Ontario|Chattanooga|Providence|Newport News|Rancho Cucamonga|Santa Rosa|Oceanside|Salem|Elk Grove|Garden Grove|Pembroke Pines|Peoria|Eugene|Corona|Cary|Springfield|Fort Collins|Jackson|Alexandria|Hayward|Lancaster|Lakewood|Clarksville|Palmdale|Salinas|Springfield|Hollywood|Pasadena|Sunnyvale|Macon|Kansas City|Pomona|Escondido|Killeen|Naperville|Joliet|Bellevue|Rockford|Savannah|Paterson|Torrance|Bridgeport|McAllen|Mesquite|Syracuse|Midland|Pasadena|Murfreesboro|Miramar|Dayton|Fullerton|Olathe|Orange|Thornton|Roseville|Denton|Waco|Surprise|Carrollton|West Valley City|Charleston|Warren|Hampton|Gainesville|Visalia|Coral Springs|Columbia|Cedar Rapids|Sterling Heights|New Haven|Stamford|Concord|Kent|Santa Clara|Elizabeth|Round Rock|Thousand Oaks|Lafayette|Athens|Topeka|Simi Valley|Fargo|Norman|Columbia|Abilene|Wilmington|Hartford|Victorville|Pearland|Vallejo|Ann Arbor|Berkeley|Allentown|Richardson|Odessa|Arvada|Cambridge|Sugar Land|Beaumont|Lansing|Evansville|Rochester|Independence|Fairfield|Provo|Clearwater|College Station|West Jordan|Carlsbad|El Monte|Murrieta|Temecula|Springfield|Palm Bay|Costa Mesa|Westminster|North Charleston|Miami Gardens|Manchester|High Point|Downey|Clovis|Pompano Beach|Pueblo|Elgin|Lowell|Antioch|West Palm Beach|Peoria|Everett|Ventura|Centennial|Lakeland|Gresham|Richmond|Billings|Inglewood|Broken Arrow|Sandy Springs|Jurupa Valley|Hillsboro|Waterbury|Santa Maria|Boulder|Greeley|Daly City|Meridian|Lewisville|Davie|West Covina|League City|Tyler|Norwalk|San Mateo|Green Bay|Wichita Falls|Sparks|Lakewood|Burbank|Rialto|Allen|Las Cruces|Vacaville|Brockton|Woodbridge|Renton|Tuscaloosa|Clinton|Fort Wayne|Edinburg)\b'
        places = re.findall(places_pattern, transcript)
        self.entities['locations'].extend(places)
        
        # Extract countries
        countries_pattern = r'\b(United States|America|Canada|Mexico|China|Russia|India|Japan|Germany|United Kingdom|Britain|France|Italy|Brazil|Australia|Spain|South Korea|Indonesia|Netherlands|Saudi Arabia|Turkey|Switzerland|Poland|Belgium|Sweden|Ireland|Argentina|Austria|UAE|Nigeria|Israel|Norway|Egypt|Denmark|Singapore|Malaysia|Philippines|South Africa|Thailand|Colombia|Pakistan|Chile|Finland|Bangladesh|Vietnam|Greece|Iraq|Algeria|Czech Republic|Portugal|Romania|Peru|New Zealand|Qatar|Kazakhstan|Hungary|Kuwait|Morocco|Ecuador|Slovakia|Angola|Ethiopia|Oman|Guatemala|Kenya|Myanmar|Luxembourg|Bulgaria|Croatia|Uruguay|Costa Rica|Panama|Lebanon|Sri Lanka|Lithuania|Serbia|Slovenia|Tunisia|Ghana|Yemen|Libya|Jordan|Ivory Coast|Bolivia|Bahrain|Cameroon|Latvia|Paraguay|Uganda|Estonia|Trinidad and Tobago|Zambia|Cyprus|Afghanistan|Nepal|Honduras|Cambodia|Iceland|Bosnia and Herzegovina|Papua New Guinea|Senegal|Zimbabwe|Georgia|Gabon|Jamaica|Mauritius|Albania|Mozambique|Malta|Burkina Faso|Namibia|Mauritania|Brunei|Botswana|Macedonia|Armenia|Madagascar|Mali|Mongolia|Bahamas|Nicaragua|Laos|Guyana|Syria|Guinea|Benin|Haiti|Moldova|Rwanda|Equatorial Guinea|Niger|Republic of the Congo|Tajikistan|Kyrgyzstan|Malawi|Chad|Fiji|Barbados|Andorra|Somalia|Togo|Monaco|Montenegro|Swaziland|Suriname|Sierra Leone|Liechtenstein|Burundi|Bhutan|San Marino|Central African Republic|Eritrea|Djibouti|Belize|Timor-Leste|Antigua and Barbuda|Liberia|Cape Verde|Seychelles|St\. Lucia|Maldives|Guinea-Bissau|St\. Vincent and the Grenadines|Solomon Islands|Comoros|Samoa|Vanuatu|St\. Kitts and Nevis|Grenada|Gambia|Micronesia|Kiribati|Tonga|Dominica|São Tomé and Príncipe|Marshall Islands|Palau|Cook Islands|Tuvalu|Nauru)\b'
        countries = re.findall(countries_pattern, transcript)
        self.entities['locations'].extend(countries)
        
        # Extract events
        event_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Conference|Summit|Meeting|Convention|Symposium|Forum|Festival|Championship|Tournament|Olympics|Awards|Ceremony))\b'
        events = re.findall(event_pattern, transcript)
        self.entities['events'].extend(events)
        
        # Extract dates/years
        year_pattern = r'\b(19\d{2}|20\d{2})\b'
        years = re.findall(year_pattern, transcript)
        self.entities['dates'].extend(years)
        
        # Remove duplicates
        for entity_type in self.entities:
            self.entities[entity_type] = list(set(self.entities[entity_type]))
    
    def _build_name_mappings(self):
        """Build mappings for name resolution"""
        # Already done in _extract_all_entities, but we can enhance here
        # Add common nicknames
        nickname_map = {
            'Bill': 'William',
            'Bob': 'Robert',
            'Dick': 'Richard',
            'Jim': 'James',
            'Joe': 'Joseph',
            'Mike': 'Michael',
            'Tom': 'Thomas',
            'Tony': 'Anthony',
            'Dan': 'Daniel',
            'Dave': 'David',
            'Steve': 'Steven',
            'Chris': 'Christopher',
            'Matt': 'Matthew',
            'Andy': 'Andrew',
            'Nick': 'Nicholas',
            'Ben': 'Benjamin',
            'Sam': 'Samuel',
            'Alex': 'Alexander',
            'Tim': 'Timothy',
            'Pat': 'Patrick',
            'Ken': 'Kenneth',
            'Greg': 'Gregory',
            'Jeff': 'Jeffrey',
            'Ron': 'Ronald',
            'Jon': 'Jonathan',
            'Ted': 'Theodore',
            'Ed': 'Edward',
            'Fred': 'Frederick',
            'Brad': 'Bradley',
            'Larry': 'Lawrence',
            'Jerry': 'Gerald',
            'Terry': 'Terrence',
            'Barry': 'Barrington',
            'Harry': 'Harold',
            'Gary': 'Gareth',
            'Rick': 'Richard',
            'Chuck': 'Charles',
            'Hank': 'Henry',
            'Frank': 'Francis',
            'Jack': 'John',
            'Will': 'William',
            'Liz': 'Elizabeth',
            'Beth': 'Elizabeth',
            'Kate': 'Katherine',
            'Katie': 'Katherine',
            'Cathy': 'Catherine',
            'Meg': 'Margaret',
            'Maggie': 'Margaret',
            'Sue': 'Susan',
            'Susie': 'Susan',
            'Jenny': 'Jennifer',
            'Jen': 'Jennifer',
            'Amy': 'Amelia',
            'Mandy': 'Amanda',
            'Sandy': 'Sandra',
            'Cindy': 'Cynthia',
            'Vicky': 'Victoria',
            'Becky': 'Rebecca',
            'Debbie': 'Deborah',
            'Jackie': 'Jacqueline',
            'Nancy': 'Ann',
            'Sally': 'Sarah',
            'Molly': 'Mary',
            'Penny': 'Penelope',
            'Lucy': 'Lucille',
            'Betty': 'Elizabeth',
            'Patty': 'Patricia'
        }
        
        # Check if any nicknames map to full names we've found
        for nickname, full_first in nickname_map.items():
            if full_first in self.name_map and nickname not in self.name_map:
                self.name_map[nickname] = self.name_map[full_first]
    
    def _extract_topics(self, transcript: str):
        """Extract main topics and themes from transcript"""
        # This could be enhanced with more sophisticated NLP
        topic_keywords = {
            'economy': ['economy', 'inflation', 'jobs', 'unemployment', 'gdp', 'growth', 'recession', 'market'],
            'healthcare': ['healthcare', 'medical', 'doctor', 'hospital', 'insurance', 'medicare', 'medicaid'],
            'education': ['education', 'school', 'teacher', 'student', 'university', 'college', 'learning'],
            'environment': ['climate', 'environment', 'pollution', 'energy', 'renewable', 'carbon', 'emissions'],
            'technology': ['technology', 'tech', 'digital', 'internet', 'ai', 'artificial intelligence', 'software'],
            'security': ['security', 'defense', 'military', 'terrorism', 'safety', 'protection', 'police'],
            'immigration': ['immigration', 'immigrant', 'border', 'citizenship', 'refugee', 'asylum'],
            'taxes': ['tax', 'taxes', 'irs', 'deduction', 'revenue', 'fiscal'],
            'crime': ['crime', 'criminal', 'prison', 'jail', 'police', 'law enforcement', 'justice'],
            'infrastructure': ['infrastructure', 'roads', 'bridges', 'transportation', 'transit', 'highway']
        }
        
        transcript_lower = transcript.lower()
        self.entities['topics'] = []
        
        for topic, keywords in topic_keywords.items():
            count = sum(1 for keyword in keywords if keyword in transcript_lower)
            if count >= 2:  # Topic mentioned at least twice
                self.entities['topics'].append(topic)
    
    def add_claim_to_context(self, claim: str):
        """Add a claim to the context history"""
        self.previous_claims.append(claim)
        if len(self.previous_claims) > self.max_context_size:
            self.previous_claims.pop(0)
    
    def resolve_context(self, claim: str) -> Tuple[str, Dict]:
        """Understand and resolve contextual references in claims"""
        original_claim = claim
        context_info = {'original': original_claim, 'resolved': False, 'resolutions': []}
        
        # Resolve partial names first
        claim = self._resolve_partial_names(claim, context_info)
        
        # Resolve pronouns
        if any(pronoun in claim.lower().split() for pronoun in ['they', 'it', 'this', 'that', 'he', 'she', 'his', 'her', 'their']):
            resolved_claim = self._resolve_pronouns(claim)
            if resolved_claim != claim:
                claim = resolved_claim
                context_info['resolved'] = True
                context_info['resolved_claim'] = claim
        
        # Handle contextual understanding
        claim = self._apply_contextual_knowledge(claim, context_info)
        
        return claim, context_info
    
    def _resolve_partial_names(self, claim: str, context_info: Dict) -> str:
        """Resolve partial names (like 'Gloria' -> 'Gloria Gaynor')"""
        words = claim.split()
        resolved_words = []
        
        for i, word in enumerate(words):
            # Check if this is a capitalized word that might be a first name
            if word[0].isupper() and word in self.name_map:
                # Check context to see if this is likely a person reference
                context_suggests_person = False
                
                # Look at surrounding words
                if i > 0:
                    prev_word = words[i-1].lower()
                    if prev_word in ['mr', 'ms', 'mrs', 'dr', 'president', 'senator', 'governor', 'mayor']:
                        context_suggests_person = True
                
                if i < len(words) - 1:
                    next_word = words[i+1].lower()
                    if next_word in ['said', 'says', 'stated', 'announced', 'won', 'lost', 'received', 'gave', 'wrote', 'created', 'invented', 'discovered', 'founded', 'directed', 'produced', 'sang', 'performed', 'acted', 'played']:
                        context_suggests_person = True
                
                # Check if the word pattern suggests a person (e.g., "Gloria won")
                if not context_suggests_person and i < len(words) - 2:
                    two_words_ahead = words[i+2].lower() if i < len(words) - 2 else ""
                    if words[i+1].lower() in ['has', 'had', 'was', 'is', 'will', 'would', 'could', 'should'] and two_words_ahead in ['won', 'lost', 'received', 'been', 'done', 'said', 'created']:
                        context_suggests_person = True
                
                # If context suggests this is a person reference
                if context_suggests_person or (i == 0 and len(self.name_map[word]) == 1):
                    # If we have exactly one person with this first name, use their full name
                    if len(self.name_map[word]) == 1:
                        full_name = self.name_map[word][0]
                        resolved_words.append(full_name)
                        context_info['resolutions'].append(f"{word} → {full_name}")
                        continue
                    elif len(self.name_map[word]) > 1:
                        # Multiple people with this first name - need more context
                        # For now, keep the original
                        resolved_words.append(word)
                        context_info['ambiguous_name'] = f"{word} could refer to: {', '.join(self.name_map[word])}"
                        continue
            
            resolved_words.append(word)
        
        return ' '.join(resolved_words)
    
    def _resolve_pronouns(self, claim: str) -> str:
        """Resolve pronoun references"""
        claim_lower = claim.lower()
        
        # Resolve "they"
        if 'they' in claim_lower:
            claim = self._resolve_they_reference(claim)
        
        # Resolve "it"
        if ' it ' in claim_lower or claim_lower.startswith('it '):
            claim = self._resolve_it_reference(claim)
        
        # Resolve "this/that"
        if 'this' in claim_lower or 'that' in claim_lower:
            claim = self._resolve_this_that_reference(claim)
        
        # Resolve "he/she/his/her"
        if any(pronoun in claim_lower for pronoun in ['he', 'she', 'his', 'her']):
            claim = self._resolve_gendered_pronouns(claim)
        
        return claim
    
    def _resolve_they_reference(self, claim: str) -> str:
        """Resolve 'they' references from context"""
        # First check previous claims
        for prev_claim in reversed(self.previous_claims[-3:]):
            # Find organization names
            orgs = re.findall(
                r'\b(?:Democrats?|Republicans?|Congress|Senate|House|'
                r'Administration|Government|Company|Corporation|'
                r'[A-Z][a-z]+\s+(?:Inc|Corp|LLC|Ltd))\b', 
                prev_claim, re.I
            )
            if orgs:
                return re.sub(r'\bthey\b', orgs[0], claim, flags=re.I)
            
            # Find people references (plural)
            people = re.findall(
                r'\b(?:senators|representatives|lawmakers|politicians|'
                r'officials|leaders|members|directors|executives)\b', 
                prev_claim, re.I
            )
            if people:
                return re.sub(r'\bthey\b', people[0], claim, flags=re.I)
        
        # Check entities from full transcript
        if self.entities.get('organizations'):
            # Use the most recently mentioned organization
            for org in self.entities['organizations']:
                if org.lower() in self.full_transcript.lower():
                    return re.sub(r'\bthey\b', org, claim, flags=re.I)
        
        return claim
    
    def _resolve_it_reference(self, claim: str) -> str:
        """Resolve 'it' references from context"""
        for prev_claim in reversed(self.previous_claims[-2:]):
            # Look for policies, bills, or things
            things = re.findall(
                r'(?:the|a)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+'
                r'(?:Act|Bill|Policy|Plan|Program|Law|Regulation|Treaty|Agreement))', 
                prev_claim
            )
            if things:
                return re.sub(r'\bit\b', things[0], claim, flags=re.I)
            
            # Look for concepts or ideas
            concepts = re.findall(
                r'(?:the|this|that)\s+([a-z]+(?:\s+[a-z]+)*)\s+(?:is|was|will|would|could|should)', 
                prev_claim.lower()
            )
            if concepts and len(concepts[0]) > 3:
                return claim.replace(' it ', f' {concepts[0]} ')
        
        return claim
    
    def _resolve_this_that_reference(self, claim: str) -> str:
        """Resolve 'this/that' references from context"""
        if not self.previous_claims:
            return claim
        
        prev = self.previous_claims[-1]
        
        # Extract the main subject from previous claim
        subjects = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', prev)
        if subjects:
            # Replace 'this' or 'that' with the most prominent subject
            main_subject = max(subjects, key=len)
            claim = re.sub(r'\bthis\b', main_subject, claim, count=1, flags=re.I)
            claim = re.sub(r'\bthat\b', main_subject, claim, count=1, flags=re.I)
        
        return claim
    
    def _resolve_gendered_pronouns(self, claim: str) -> str:
        """Resolve he/she/his/her pronouns"""
        # Look for the most recent person mentioned
        recent_person = None
        
        # Check previous claims
        for prev_claim in reversed(self.previous_claims[-3:]):
            for person in self.entities.get('people', []):
                if person in prev_claim:
                    recent_person = person
                    break
            if recent_person:
                break
        
        if recent_person:
            # Simple gender inference based on common names
            # This is imperfect but better than nothing
            male_names = ['John', 'James', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Charles', 'Donald', 'Joe', 'Barack', 'Bill', 'George', 'Ronald', 'Jimmy']
            female_names = ['Mary', 'Patricia', 'Jennifer', 'Linda', 'Elizabeth', 'Barbara', 'Susan', 'Jessica', 'Sarah', 'Karen', 'Hillary', 'Nancy', 'Michelle', 'Laura', 'Gloria']
            
            first_name = recent_person.split()[0]
            
            if first_name in male_names:
                claim = re.sub(r'\bhe\b', recent_person, claim, flags=re.I)
                claim = re.sub(r'\bhis\b', f"{recent_person}'s", claim, flags=re.I)
            elif first_name in female_names:
                claim = re.sub(r'\bshe\b', recent_person, claim, flags=re.I)
                claim = re.sub(r'\bher\b', f"{recent_person}'s", claim, flags=re.I)
        
        return claim
    
    def _apply_contextual_knowledge(self, claim: str, context_info: Dict) -> str:
        """Apply domain-specific contextual understanding"""
        claim_lower = claim.lower()
        
        # Sports context
        golf_terms = ['putting', 'golf', 'pga', 'masters', 'tournament', 'birdie', 'eagle', 'par']
        if 'tiger' in claim_lower and any(term in claim_lower for term in golf_terms):
            claim = re.sub(r'\btiger\b', 'Tiger Woods', claim, flags=re.I)
            context_info['inferred_subject'] = 'Tiger Woods (golfer)'
        
        # Political context
        if 'the president' in claim_lower and not any(name in claim for name in ['Biden', 'Trump', 'Obama']):
            # Check if we can infer from context
            for president in ['Joe Biden', 'Donald Trump', 'Barack Obama']:
                if president in self.full_transcript:
                    claim = claim.replace('the president', president)
                    claim = claim.replace('The President', president)
                    claim = claim.replace('The president', president)
                    context_info['inferred_subject'] = president
                    break
        
        # Economic context
        if 'the fed' in claim_lower:
            claim = claim.replace('the fed', 'the Federal Reserve')
            claim = claim.replace('The Fed', 'The Federal Reserve')
            context_info['expanded'] = 'Federal Reserve'
        
        # Tech context
        tech_abbreviations = {
            'ai': 'artificial intelligence',
            'ml': 'machine learning',
            'api': 'application programming interface',
            'ui': 'user interface',
            'ux': 'user experience',
            'iot': 'internet of things',
            'vr': 'virtual reality',
            'ar': 'augmented reality'
        }
        
        for abbrev, full in tech_abbreviations.items():
            if f' {abbrev} ' in claim_lower or claim_lower.startswith(f'{abbrev} ') or claim_lower.endswith(f' {abbrev}'):
                # Use word boundaries for replacement
                pattern = r'\b' + abbrev + r'\b'
                claim = re.sub(pattern, full, claim, flags=re.I)
                context_info['expanded'] = full
        
        # Awards context - handle cases like "Grammy" without year
        award_terms = ['grammy', 'oscar', 'emmy', 'tony', 'pulitzer', 'nobel']
        for award in award_terms:
            if award in claim_lower:
                # Check if a year is mentioned nearby in the transcript
                year_pattern = r'\b(19\d{2}|20\d{2})\b'
                years = re.findall(year_pattern, self.full_transcript)
                if years and award in claim_lower:
                    # Find the year closest to this award mention
                    context_info['award_context'] = f"{award.title()} (years mentioned in transcript: {', '.join(set(years))})"
        
        return claim
    
    def check_vagueness(self, claim: str) -> Dict:
        """Check if a claim is too vague to verify"""
        claim_lower = claim.lower()
        
        # Vague pronouns without clear antecedents
        if claim_lower.startswith(('they ', 'it ', 'this ', 'that ')) and len(self.previous_claims) == 0:
            return {'is_vague': True, 'reason': 'Unclear pronoun reference without context'}
        
        # Too short
        if len(claim.split()) < 5:
            return {'is_vague': True, 'reason': 'Claim too brief to verify'}
        
        # No specific claims
        vague_phrases = [
            'some people say', 'everyone knows', 'it is said', 
            'many believe', 'they say', 'people think', 'sources say',
            'experts believe', 'studies show', 'research indicates'
        ]
        
        for phrase in vague_phrases:
            if phrase in claim_lower and not any(
                specific in claim for specific in ['%', 'percent', 'million', 'billion', '$']
            ):
                return {'is_vague': True, 'reason': f'Vague attribution: "{phrase}"'}
        
        # Pure opinion
        opinion_words = ['beautiful', 'amazing', 'terrible', 'wonderful', 'horrible', 'best', 'worst']
        if any(word in claim_lower for word in opinion_words) and not any(char.isdigit() for char in claim):
            return {'is_vague': True, 'reason': 'Subjective opinion rather than factual claim'}
        
        return {'is_vague': False}
    
    def extract_claim_source(self, claim: str) -> Optional[str]:
        """Extract who is making the claim"""
        patterns = [
            # "According to X"
            r'(?:According to|Says?|Claims?|States?|Reported by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            # "X said/claims"
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:said|says|claimed|claims|stated|states|reported|reports)',
            # "X: [claim]"
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*):',
            # Quoted sources
            r'"[^"]+"\s*[-—]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            # News organizations
            r'\b(CNN|Fox News|MSNBC|Reuters|AP|BBC|NPR|The New York Times|The Washington Post)\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, claim, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def get_context_summary(self) -> Dict:
        """Get a summary of the extracted context"""
        return {
            'people': len(self.entities.get('people', [])),
            'organizations': len(self.entities.get('organizations', [])),
            'locations': len(self.entities.get('locations', [])),
            'events': len(self.entities.get('events', [])),
            'topics': self.entities.get('topics', []),
            'name_mappings': len(self.name_map),
            'total_entities': sum(len(v) for v in self.entities.values())
        }

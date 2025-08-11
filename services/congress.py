"""
Congressional Data Service
Handles congressman lookup, speeches, voting records, and campaign finance
"""
import os
import re
import json
import logging
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import quote
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

class CongressionalService:
    """Service for accessing congressional data from multiple sources"""
    
    def __init__(self):
        # API Keys
        self.propublica_api_key = os.getenv('PROPUBLICA_API_KEY')
        self.fec_api_key = os.getenv('FEC_API_KEY')
        self.congress_api_key = os.getenv('CONGRESS_API_KEY')
        
        # Current Congress session (118th Congress: 2023-2025)
        self.current_congress = 118
        
        # State abbreviations for lookup
        self.state_abbr = {
            'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
            'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
            'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
            'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
            'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
            'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
            'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
            'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
            'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
            'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
            'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
            'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
            'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC'
        }
        
        # Validate configuration
        self._validate_apis()
    
    def _validate_apis(self):
        """Log available APIs"""
        available = []
        if self.propublica_api_key:
            available.append("ProPublica Congress API")
        if self.fec_api_key:
            available.append("FEC Campaign Finance API")
        if self.congress_api_key:
            available.append("Congress.gov API")
        
        if available:
            logger.info(f"Congressional APIs available: {', '.join(available)}")
        else:
            logger.warning("No congressional APIs configured - using limited public data")
    
    def find_representatives_by_zip(self, zip_code: str) -> Dict:
        """Find representatives by ZIP code"""
        try:
            # First, get location info from ZIP
            location = self._get_location_from_zip(zip_code)
            if not location:
                return {'error': 'Invalid ZIP code'}
            
            state = location['state']
            
            # Get senators (same for whole state)
            senators = self._get_senators(state)
            
            # Get house representative (need more specific location)
            representatives = self._get_representatives_by_zip(zip_code)
            
            return {
                'success': True,
                'location': location,
                'senators': senators,
                'representatives': representatives
            }
            
        except Exception as e:
            logger.error(f"Error finding representatives: {str(e)}")
            return {'error': str(e)}
    
    def find_representatives_by_address(self, address: str) -> Dict:
        """Find representatives by street address"""
        try:
            # Use Google Civic Info API (free tier available)
            if not address:
                return {'error': 'Address required'}
            
            # This would use Google Civic Info API
            # For now, extract ZIP from address if possible
            zip_match = re.search(r'\b(\d{5})(?:-\d{4})?\b', address)
            if zip_match:
                return self.find_representatives_by_zip(zip_match.group(1))
            
            return {'error': 'Could not parse address. Please include ZIP code.'}
            
        except Exception as e:
            logger.error(f"Error finding representatives by address: {str(e)}")
            return {'error': str(e)}
    
    def get_member_details(self, member_id: str) -> Dict:
        """Get detailed information about a member of Congress"""
        try:
            member_data = {}
            
            # Get basic info from ProPublica
            if self.propublica_api_key:
                propublica_data = self._get_propublica_member(member_id)
                if propublica_data:
                    member_data.update(propublica_data)
            
            # Get additional data from Congress.gov
            if self.congress_api_key:
                congress_data = self._get_congress_gov_member(member_id)
                if congress_data:
                    member_data.update(congress_data)
            
            # If no API data, use basic fallback
            if not member_data:
                member_data = self._get_fallback_member_data(member_id)
            
            return {
                'success': True,
                'member': member_data
            }
            
        except Exception as e:
            logger.error(f"Error getting member details: {str(e)}")
            return {'error': str(e)}
    
    def get_member_speeches(self, member_id: str, limit: int = 20) -> Dict:
        """Get recent speeches and statements from a member"""
        try:
            speeches = []
            
            # Get from Congress.gov API
            if self.congress_api_key:
                congress_speeches = self._get_congress_speeches(member_id, limit)
                speeches.extend(congress_speeches)
            
            # Get from Congressional Record
            cr_speeches = self._get_congressional_record_speeches(member_id, limit)
            speeches.extend(cr_speeches)
            
            # Sort by date (most recent first)
            speeches.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            return {
                'success': True,
                'member_id': member_id,
                'speeches': speeches[:limit],
                'total_found': len(speeches)
            }
            
        except Exception as e:
            logger.error(f"Error getting speeches: {str(e)}")
            return {'error': str(e)}
    
    def get_voting_record(self, member_id: str, limit: int = 50) -> Dict:
        """Get recent voting record for a member"""
        try:
            votes = []
            
            if self.propublica_api_key:
                # Get voting record from ProPublica
                votes = self._get_propublica_votes(member_id, limit)
            else:
                # Fallback to public data
                votes = self._get_public_voting_data(member_id, limit)
            
            # Analyze voting patterns
            analysis = self._analyze_voting_patterns(votes)
            
            return {
                'success': True,
                'member_id': member_id,
                'votes': votes,
                'total_votes': len(votes),
                'analysis': analysis
            }
            
        except Exception as e:
            logger.error(f"Error getting voting record: {str(e)}")
            return {'error': str(e)}
    
    def get_campaign_finance(self, member_name: str) -> Dict:
        """Get campaign finance data for a member"""
        try:
            finance_data = {
                'total_raised': 0,
                'total_spent': 0,
                'cash_on_hand': 0,
                'top_contributors': [],
                'contribution_breakdown': {},
                'last_updated': None
            }
            
            if self.fec_api_key:
                # Get FEC data
                fec_data = self._get_fec_data(member_name)
                if fec_data:
                    finance_data.update(fec_data)
            
            # Get OpenSecrets data (if available)
            opensecrets_data = self._get_opensecrets_data(member_name)
            if opensecrets_data:
                finance_data['opensecrets'] = opensecrets_data
            
            return {
                'success': True,
                'member_name': member_name,
                'finance': finance_data
            }
            
        except Exception as e:
            logger.error(f"Error getting campaign finance: {str(e)}")
            return {'error': str(e)}
    
    def download_speeches_pdf(self, member_id: str, speech_ids: List[str]) -> Optional[bytes]:
        """Generate PDF of selected speeches"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from io import BytesIO
            
            # Get member info
            member_result = self.get_member_details(member_id)
            if not member_result.get('success'):
                return None
            
            member = member_result['member']
            
            # Get speeches
            speeches_result = self.get_member_speeches(member_id, limit=100)
            if not speeches_result.get('success'):
                return None
            
            # Filter to requested speeches
            all_speeches = speeches_result['speeches']
            selected_speeches = [s for s in all_speeches if s.get('id') in speech_ids]
            
            if not selected_speeches:
                return None
            
            # Create PDF
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Title'],
                fontSize=24,
                spaceAfter=30
            )
            story.append(Paragraph(f"Congressional Speeches - {member['name']}", title_style))
            story.append(Spacer(1, 0.5*inch))
            
            # Member info
            info_text = f"""
            <b>Member:</b> {member['name']}<br/>
            <b>State:</b> {member.get('state', 'N/A')}<br/>
            <b>Party:</b> {member.get('party', 'N/A')}<br/>
            <b>Chamber:</b> {member.get('chamber', 'N/A')}<br/>
            <b>Generated:</b> {datetime.now().strftime('%B %d, %Y')}
            """
            story.append(Paragraph(info_text, styles['Normal']))
            story.append(Spacer(1, 0.5*inch))
            
            # Add each speech
            for i, speech in enumerate(selected_speeches, 1):
                # Speech header
                header = f"<b>Speech {i}: {speech.get('title', 'Untitled')}</b>"
                story.append(Paragraph(header, styles['Heading2']))
                
                # Speech metadata
                meta = f"""
                <b>Date:</b> {speech.get('date', 'N/A')}<br/>
                <b>Location:</b> {speech.get('location', 'Congressional Record')}<br/>
                <b>Type:</b> {speech.get('type', 'Floor Speech')}
                """
                story.append(Paragraph(meta, styles['Normal']))
                story.append(Spacer(1, 0.2*inch))
                
                # Speech content
                content = speech.get('content', speech.get('summary', 'Content not available'))
                # Clean up content
                content = re.sub(r'<[^>]+>', '', content)  # Remove HTML
                content = content.replace('&nbsp;', ' ')
                content = content.replace('&amp;', '&')
                
                story.append(Paragraph(content, styles['Normal']))
                
                if i < len(selected_speeches):
                    story.append(PageBreak())
            
            # Build PDF
            doc.build(story)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            return pdf_data
            
        except Exception as e:
            logger.error(f"Error generating speeches PDF: {str(e)}")
            return None
    
    # Private helper methods
    
    def _get_location_from_zip(self, zip_code: str) -> Optional[Dict]:
        """Get city and state from ZIP code"""
        try:
            # Use free ZIP code API
            response = requests.get(f"https://api.zippopotam.us/us/{zip_code}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    'zip': zip_code,
                    'city': data.get('places', [{}])[0].get('place name', ''),
                    'state': data.get('places', [{}])[0].get('state', ''),
                    'state_abbr': data.get('places', [{}])[0].get('state abbreviation', '')
                }
            return None
        except Exception as e:
            logger.error(f"Error getting location from ZIP: {str(e)}")
            return None
    
    def _get_senators(self, state: str) -> List[Dict]:
        """Get senators for a state"""
        senators = []
        
        if self.propublica_api_key:
            try:
                headers = {'X-API-Key': self.propublica_api_key}
                url = f"https://api.propublica.org/congress/v1/members/senate/{state}/current.json"
                
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    for member in data.get('results', []):
                        senators.append({
                            'name': member['name'],
                            'party': member['party'],
                            'id': member['id'],
                            'next_election': member.get('next_election', ''),
                            'office': member.get('office', ''),
                            'phone': member.get('phone', ''),
                            'website': member.get('url', '')
                        })
            except Exception as e:
                logger.error(f"Error getting senators: {str(e)}")
        
        # Fallback data if API fails
        if not senators:
            # This would have hardcoded current senators
            # For demo purposes, return empty
            pass
        
        return senators
    
    def _get_representatives_by_zip(self, zip_code: str) -> List[Dict]:
        """Get house representatives by ZIP code"""
        representatives = []
        
        # Note: ZIP codes can span multiple districts
        # Ideally use Google Civic Info API or similar
        
        # For now, return message about needing full address
        if not self.propublica_api_key:
            representatives.append({
                'note': 'Full address needed for accurate House representative lookup',
                'reason': 'ZIP codes can span multiple congressional districts'
            })
        
        return representatives
    
    def _get_propublica_member(self, member_id: str) -> Optional[Dict]:
        """Get member data from ProPublica API"""
        try:
            headers = {'X-API-Key': self.propublica_api_key}
            url = f"https://api.propublica.org/congress/v1/members/{member_id}.json"
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                member = data['results'][0]
                
                return {
                    'name': member['first_name'] + ' ' + member['last_name'],
                    'party': member['current_party'],
                    'state': member['roles'][0]['state'],
                    'chamber': member['roles'][0]['chamber'],
                    'title': member['roles'][0]['title'],
                    'office': member['roles'][0]['office'],
                    'phone': member['roles'][0]['phone'],
                    'website': member['url'],
                    'twitter': member.get('twitter_account', ''),
                    'facebook': member.get('facebook_account', ''),
                    'youtube': member.get('youtube_account', ''),
                    'next_election': member['roles'][0].get('next_election', ''),
                    'votes_with_party_pct': member['roles'][0].get('votes_with_party_pct', 0),
                    'missed_votes_pct': member['roles'][0].get('missed_votes_pct', 0)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"ProPublica API error: {str(e)}")
            return None
    
    def _get_congress_speeches(self, member_id: str, limit: int) -> List[Dict]:
        """Get speeches from Congress.gov API"""
        speeches = []
        
        if not self.congress_api_key:
            return speeches
        
        try:
            # Congress.gov API endpoint for member statements
            headers = {'X-API-Key': self.congress_api_key}
            url = f"https://api.congress.gov/v3/member/{member_id}/statements"
            params = {'limit': limit, 'format': 'json'}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                for statement in data.get('statements', []):
                    speeches.append({
                        'id': statement.get('id'),
                        'date': statement.get('date'),
                        'title': statement.get('title'),
                        'type': statement.get('type'),
                        'content': statement.get('text', ''),
                        'url': statement.get('url'),
                        'source': 'Congress.gov'
                    })
            
        except Exception as e:
            logger.error(f"Congress.gov API error: {str(e)}")
        
        return speeches
    
    def _get_congressional_record_speeches(self, member_id: str, limit: int) -> List[Dict]:
        """Get speeches from Congressional Record"""
        speeches = []
        
        # This would scrape or use API for Congressional Record
        # For now, return empty list
        
        return speeches
    
    def _get_propublica_votes(self, member_id: str, limit: int) -> List[Dict]:
        """Get voting record from ProPublica"""
        votes = []
        
        try:
            headers = {'X-API-Key': self.propublica_api_key}
            url = f"https://api.propublica.org/congress/v1/members/{member_id}/votes.json"
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                for vote in data['results'][0]['votes'][:limit]:
                    votes.append({
                        'bill_id': vote.get('bill', {}).get('bill_id'),
                        'bill_title': vote.get('bill', {}).get('title', vote.get('description')),
                        'date': vote.get('date'),
                        'position': vote.get('position'),
                        'result': vote.get('result'),
                        'question': vote.get('question'),
                        'vote_type': vote.get('vote_type'),
                        'party_split': self._get_party_split(vote)
                    })
            
        except Exception as e:
            logger.error(f"Error getting ProPublica votes: {str(e)}")
        
        return votes
    
    def _get_party_split(self, vote: Dict) -> Dict:
        """Calculate party split for a vote"""
        split = {
            'democratic': {'yes': 0, 'no': 0},
            'republican': {'yes': 0, 'no': 0}
        }
        
        # Extract from vote data if available
        if 'democratic' in vote:
            split['democratic'] = vote['democratic']
        if 'republican' in vote:
            split['republican'] = vote['republican']
        
        return split
    
    def _analyze_voting_patterns(self, votes: List[Dict]) -> Dict:
        """Analyze voting patterns"""
        analysis = {
            'total_votes': len(votes),
            'party_line_votes': 0,
            'bipartisan_votes': 0,
            'key_issues': {},
            'voting_frequency': {}
        }
        
        # Analyze each vote
        for vote in votes:
            # Check if vote was along party lines
            party_split = vote.get('party_split', {})
            # Add analysis logic here
        
        return analysis
    
    def _get_fec_data(self, member_name: str) -> Optional[Dict]:
        """Get campaign finance data from FEC"""
        try:
            # Search for candidate
            search_url = "https://api.open.fec.gov/v1/candidates/search/"
            params = {
                'q': member_name,
                'api_key': self.fec_api_key,
                'per_page': 10
            }
            
            response = requests.get(search_url, params=params, timeout=10)
            if response.status_code != 200:
                return None
            
            data = response.json()
            if not data.get('results'):
                return None
            
            # Get first matching candidate
            candidate = data['results'][0]
            candidate_id = candidate['candidate_id']
            
            # Get financial summary
            finance_url = f"https://api.open.fec.gov/v1/candidate/{candidate_id}/totals/"
            params = {'api_key': self.fec_api_key}
            
            response = requests.get(finance_url, params=params, timeout=10)
            if response.status_code == 200:
                finance_data = response.json()
                if finance_data.get('results'):
                    latest = finance_data['results'][0]
                    
                    return {
                        'total_raised': latest.get('receipts', 0),
                        'total_spent': latest.get('disbursements', 0),
                        'cash_on_hand': latest.get('cash_on_hand_end_period', 0),
                        'debt': latest.get('debts_owed_by_committee', 0),
                        'individual_contributions': latest.get('individual_contributions', 0),
                        'pac_contributions': latest.get('other_political_committee_contributions', 0),
                        'last_updated': latest.get('coverage_end_date'),
                        'cycle': latest.get('cycle')
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"FEC API error: {str(e)}")
            return None
    
    def _get_opensecrets_data(self, member_name: str) -> Optional[Dict]:
        """Get data from OpenSecrets (if API key available)"""
        # OpenSecrets requires paid API access
        # This is a placeholder for future implementation
        return None
    
    def _get_public_voting_data(self, member_id: str, limit: int) -> List[Dict]:
        """Fallback method to get public voting data"""
        # This would scrape public sources
        # For now, return empty list
        return []
    
    def _get_congress_gov_member(self, member_id: str) -> Optional[Dict]:
        """Get additional member data from Congress.gov"""
        # Implementation would use Congress.gov API
        return None
    
    def _get_fallback_member_data(self, member_id: str) -> Dict:
        """Basic fallback data when APIs unavailable"""
        return {
            'id': member_id,
            'name': 'Member data unavailable',
            'note': 'Configure API keys for full congressional data access'
        }

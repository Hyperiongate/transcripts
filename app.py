def process_transcript(job_id, transcript, source):
    """Process transcript through the fact-checking pipeline"""
    try:
        # Ensure job exists
        if not job_storage.exists(job_id):
            logger.error(f"Job {job_id} not found in job storage")
            return
        
        # Clean transcript
        job_storage.update(job_id, {'progress': 20})
        cleaned_transcript = transcript_processor.clean_transcript(transcript)
        
        # Identify speakers and topics
        job_storage.update(job_id, {'progress': 30})
        speakers, topics = claim_extractor.identify_speakers(transcript)
        
        # Log speaker identification results properly
        if speakers:
            logger.info(f"Job {job_id}: Identified speakers: {speakers[:5]}")  # Show first 5
        else:
            logger.info(f"Job {job_id}: No specific speakers identified")
        
        if topics:
            logger.info(f"Job {job_id}: Key topics: {topics}")
        
        # Extract claims
        job_storage.update(job_id, {'progress': 40})
        claims = claim_extractor.extract_claims(cleaned_transcript)
        logger.info(f"Job {job_id}: Extracted {len(claims)} claims")
        
        # Prioritize and filter claims
        job_storage.update(job_id, {'progress': 50})
        verified_claims = claim_extractor.filter_verifiable(claims)
        prioritized_claims = claim_extractor.prioritize_claims(verified_claims)
        logger.info(f"Job {job_id}: Checking {len(prioritized_claims)} prioritized claims")
        
        # Ensure we have strings, not dictionaries
        if prioritized_claims and isinstance(prioritized_claims[0], dict):
            logger.warning("Claims are dictionaries, extracting text")
            prioritized_claims = [claim['text'] if isinstance(claim, dict) else claim for claim in prioritized_claims]
        
        # Fact check claims
        job_storage.update(job_id, {'progress': 70})
        fact_check_results = []
        
        # Use batch_check but with error handling for individual claims
        claims_to_check = prioritized_claims[:Config.MAX_CLAIMS_PER_TRANSCRIPT]
        
        for i in range(0, len(claims_to_check), Config.FACT_CHECK_BATCH_SIZE):
            batch = claims_to_check[i:i + Config.FACT_CHECK_BATCH_SIZE]
            try:
                batch_results = fact_checker.batch_check(batch)
                fact_check_results.extend(batch_results)
                # Update progress
                progress = 70 + int((len(fact_check_results) / len(claims_to_check)) * 20)
                job_storage.update(job_id, {'progress': progress})
            except Exception as e:
                logger.error(f"Error checking batch starting at {i}: {str(e)}")
                # Add unverified results for failed batch
                for claim in batch:
                    fact_check_results.append({
                        'claim': claim,
                        'verdict': 'unverified',
                        'confidence': 0,
                        'explanation': 'Error during fact-checking',
                        'publisher': 'Error',
                        'url': '',
                        'sources': []
                    })
        
        # Calculate overall credibility
        job_storage.update(job_id, {'progress': 90})
        credibility_score = fact_checker.calculate_credibility(fact_check_results)
        
        # Generate enhanced summary with speaker/topic info
        summary = generate_summary(fact_check_results, credibility_score)
        if speakers:
            summary += f" Main speakers identified: {', '.join(speakers[:3])}."
        if topics:
            summary += f" Key topics: {', '.join(topics)}."
        
        # Compile results
        results = {
            'source': source,
            'transcript_length': len(transcript),
            'word_count': len(transcript.split()),
            'speakers': speakers[:10] if speakers else [],  # Limit to top 10
            'topics': topics,
            'total_claims': len(claims),
            'verified_claims': len(verified_claims),
            'checked_claims': len(fact_check_results),
            'credibility_score': credibility_score,
            'credibility_label': get_credibility_label(credibility_score),
            'fact_checks': fact_check_results,
            'summary': summary,
            'analyzed_at': datetime.now().isoformat()
        }
        
        # Add analysis notes if no API keys
        if not Config.GOOGLE_FACTCHECK_API_KEY:
            results['analysis_notes'] = [
                "Running in demo mode - no fact-checking APIs configured",
                "Results shown are simulated for demonstration purposes",
                "Configure API keys in .env file for real fact-checking"
            ]
        
        # Complete job
        job_storage.update(job_id, {
            'progress': 100,
            'status': 'complete',
            'results': results
        })
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {str(e)}")
        logger.error(traceback.format_exc())
        job_storage.update(job_id, {
            'status': 'error',
            'error': str(e)
        })

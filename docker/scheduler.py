# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Scheduler service that simulates AWS EventBridge.
Triggers plan generation on a cron schedule.
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
import jwt
from croniter import croniter

# Configure logging
logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/scheduler.log')
    ]
)
logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.api_url = os.environ.get('API_URL', 'http://api:8000')
        self.jwt_secret = os.environ.get('JWT_SECRET', 'dev-secret-change-in-production')
        self.cron_schedule = os.environ.get('SCHEDULE_CRON', '0 7 * * 1-5')  # 7 AM weekdays
        self.check_interval = 60  # Check every minute
        
        logger.info(f"Scheduler initialized")
        logger.info(f"API URL: {self.api_url}")
        logger.info(f"Cron schedule: {self.cron_schedule}")
    
    def generate_token(self) -> str:
        """Generate JWT token for API authentication."""
        payload = {
            'sub': 'scheduler',
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=1)
        }
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')
    
    def trigger_plan_generation(self) -> bool:
        """Trigger plan generation via API."""
        try:
            token = self.generate_token()
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'date': datetime.now().date().isoformat()
            }
            
            logger.info(f"Triggering plan generation for {payload['date']}")
            
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.api_url}/api/v1/plan",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    logger.info("Plan generation successful")
                    logger.debug(f"Response: {response.json()}")
                    return True
                else:
                    logger.error(f"Plan generation failed: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error triggering plan generation: {e}", exc_info=True)
            return False
    
    def wait_for_api(self, max_retries: int = 30, retry_interval: int = 2):
        """Wait for API to be ready."""
        logger.info("Waiting for API to be ready...")
        
        for i in range(max_retries):
            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(f"{self.api_url}/api/v1/health")
                    if response.status_code == 200:
                        logger.info("API is ready")
                        return True
            except Exception as e:
                logger.debug(f"API not ready yet (attempt {i+1}/{max_retries}): {e}")
            
            time.sleep(retry_interval)
        
        logger.error("API failed to become ready")
        return False
    
    def run(self):
        """Run the scheduler loop."""
        # Wait for API to be ready
        if not self.wait_for_api():
            logger.error("Exiting: API not available")
            sys.exit(1)
        
        logger.info("Starting scheduler loop")
        
        # Initialize croniter
        cron = croniter(self.cron_schedule, datetime.now())
        next_run = cron.get_next(datetime)
        logger.info(f"Next scheduled run: {next_run}")
        
        last_run: Optional[datetime] = None
        
        while True:
            try:
                now = datetime.now()
                
                # Check if it's time to run
                if now >= next_run:
                    # Avoid duplicate runs within the same minute
                    if last_run is None or (now - last_run).total_seconds() > 60:
                        logger.info(f"Executing scheduled task at {now}")
                        self.trigger_plan_generation()
                        last_run = now
                    
                    # Calculate next run
                    next_run = cron.get_next(datetime)
                    logger.info(f"Next scheduled run: {next_run}")
                
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Scheduler stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                time.sleep(self.check_interval)

if __name__ == "__main__":
    scheduler = Scheduler()
    scheduler.run()

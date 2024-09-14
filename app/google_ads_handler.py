# app/google_ads_handler.py

from google.ads.googleads.client import GoogleAdsClient
from app.models import GoogleAdsAccount, GoogleAdsCampaign
from app.database import db

class GoogleAdsHandler:
    def __init__(self, credentials_path):
        self.client = GoogleAdsClient.load_from_storage(credentials_path)

    def sync_campaigns(self, agency_id):
        google_ads_accounts = GoogleAdsAccount.query.filter_by(agency_id=agency_id).all()
        for account in google_ads_accounts:
            customer_id = account.customer_id
            ga_service = self.client.get_service("GoogleAdsService")
            query = """
                SELECT
                  campaign.id,
                  campaign.name,
                  campaign.status,
                  campaign_budget.amount_micros
                FROM campaign
            """
            stream = ga_service.search_stream(customer_id=customer_id, query=query)

            for batch in stream:
                for row in batch.results:
                    campaign = row.campaign
                    budget = row.campaign_budget
                    existing_campaign = GoogleAdsCampaign.query.filter_by(campaign_id=str(campaign.id)).first()
                    if existing_campaign:
                        existing_campaign.name = campaign.name
                        existing_campaign.status = campaign.status.name
                        existing_campaign.budget = budget.amount_micros / 1_000_000
                    else:
                        new_campaign = GoogleAdsCampaign(
                            campaign_id=str(campaign.id),
                            name=campaign.name,
                            status=campaign.status.name,
                            budget=budget.amount_micros / 1_000_000,
                            account_id=account.id
                        )
                        db.session.add(new_campaign)
            
            db.session.commit()

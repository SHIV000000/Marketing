# Marketing\app\google_ads\google_ads_handler.py

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from app.models import GoogleAdsAccount, GoogleAdsCampaign
from app.database import db
from flask import current_app
import os

class GoogleAdsHandler:
    def __init__(self):
        self.client = self._create_google_ads_client()

    def _create_google_ads_client(self):
        try:
            return GoogleAdsClient.load_from_storage(os.getenv('GOOGLE_ADS_YAML_FILE_PATH'))
        except Exception as e:
            current_app.logger.error(f"Error initializing Google Ads client: {str(e)}")
            raise

    def sync_campaigns(self, agency_id):
        google_ads_accounts = GoogleAdsAccount.query.filter_by(agency_id=agency_id).all()
        for account in google_ads_accounts:
            try:
                self._sync_account_campaigns(account)
            except GoogleAdsException as ex:
                current_app.logger.error(
                    f'Request with ID "{ex.request_id}" failed with status '
                    f'"{ex.error.code().name}" and includes the following errors:'
                )
                for error in ex.failure.errors:
                    current_app.logger.error(f'\tError with message "{error.message}".')
                    if error.location:
                        for field_path_element in error.location.field_path_elements:
                            current_app.logger.error(f"\t\tOn field: {field_path_element.field_name}")
            except Exception as e:
                current_app.logger.error(f"Error syncing campaigns for account {account.id}: {str(e)}")

    def _sync_account_campaigns(self, account):
        customer_id = account.customer_id
        ga_service = self.client.get_service("GoogleAdsService")
        query = """
            SELECT
              campaign.id,
              campaign.name,
              campaign.status,
              campaign_budget.amount_micros,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros
            FROM campaign
            WHERE segments.date DURING LAST_30_DAYS
        """
        stream = ga_service.search_stream(customer_id=customer_id, query=query)

        for batch in stream:
            for row in batch.results:
                campaign = row.campaign
                budget = row.campaign_budget
                metrics = row.metrics
                
                existing_campaign = GoogleAdsCampaign.query.filter_by(
                    campaign_id=str(campaign.id),
                    account_id=account.id
                ).first()
                
                if existing_campaign:
                    self._update_campaign(existing_campaign, campaign, budget, metrics)
                else:
                    new_campaign = self._create_campaign(campaign, budget, metrics, account.id)
                    db.session.add(new_campaign)

        db.session.commit()

    def _update_campaign(self, existing_campaign, campaign, budget, metrics):
        existing_campaign.name = campaign.name
        existing_campaign.status = campaign.status.name
        existing_campaign.budget = budget.amount_micros / 1_000_000
        existing_campaign.impressions = metrics.impressions
        existing_campaign.clicks = metrics.clicks
        existing_campaign.cost = metrics.cost_micros / 1_000_000

    def _create_campaign(self, campaign, budget, metrics, account_id):
        return GoogleAdsCampaign(
            campaign_id=str(campaign.id),
            name=campaign.name,
            status=campaign.status.name,
            budget=budget.amount_micros / 1_000_000,
            impressions=metrics.impressions,
            clicks=metrics.clicks,
            cost=metrics.cost_micros / 1_000_000,
            account_id=account_id
        )

    def get_account_performance(self, account_id):
        account = GoogleAdsAccount.query.get(account_id)
        if not account:
            return None

        try:
            customer_id = account.customer_id
            ga_service = self.client.get_service("GoogleAdsService")
            query = """
                SELECT
                  customer.descriptive_name,
                  metrics.impressions,
                  metrics.clicks,
                  metrics.cost_micros
                FROM customer
                WHERE segments.date DURING LAST_30_DAYS
            """
            response = ga_service.search(customer_id=customer_id, query=query)

            for row in response:
                return {
                    'name': row.customer.descriptive_name,
                    'impressions': row.metrics.impressions,
                    'clicks': row.metrics.clicks,
                    'cost': row.metrics.cost_micros / 1_000_000
                }
        except GoogleAdsException as ex:
            current_app.logger.error(f"Google Ads API error occurred: {ex}")
        except Exception as e:
            current_app.logger.error(f"Error fetching account performance: {str(e)}")

        return None

    def link_google_ads_account(self, agency_id, customer_id, refresh_token):
        try:
            # Validate the customer_id and refresh_token with Google Ads API
            self.client.oauth2.refresh_token = refresh_token
            self.client.get_service("GoogleAdsService").search(
                customer_id=customer_id,
                query="SELECT customer.id FROM customer LIMIT 1"
            )

            new_account = GoogleAdsAccount(
                customer_id=customer_id,
                refresh_token=refresh_token,
                agency_id=agency_id
            )
            db.session.add(new_account)
            db.session.commit()
            return True
        except GoogleAdsException as ex:
            current_app.logger.error(f"Google Ads API error occurred: {ex}")
        except Exception as e:
            current_app.logger.error(f"Error linking Google Ads account: {str(e)}")
        
        return False

'''
Subscription database operation DTOs.
'''

from typing import Optional
from pydantic import BaseModel


class GetSubscriptionPlanModel(BaseModel):
    """Model for getting a subscription plan."""
    subscription_id: str
    subscription_type_id: str


class CreateFreeSubscriptionModel(BaseModel):
    """Model for creating a free subscription."""
    user_id: str


class GetOrCreateSubscriptionModel(BaseModel):
    """Model for getting or creating a subscription."""
    user_id: str


class GetUserSubscriptionPlanModel(BaseModel):
    """Model for getting a user's current subscription plan."""
    user_id: str


class UpdateSubscriptionModel(BaseModel):
    """Model for updating a subscription."""
    user_id: str
    subscription_type: str

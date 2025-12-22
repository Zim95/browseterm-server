'''
Image database operation DTOs.
'''

from typing import Optional
from pydantic import BaseModel, Field, model_validator


class GetImageDataModel(BaseModel):
    '''
    Filters for fetching a single image.

    Only the following fields are supported:
    - id: Image ID (UUID as string)
    - name: Image name (string)
    - image: Image reference/tag (string)

    At least one field must be provided.
    '''
    id: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    image: Optional[str] = Field(default=None)

    @model_validator(mode='after')
    def validate_at_least_one(self) -> 'GetImageDataModel':
        if not (self.id or self.name or self.image):
            raise ValueError("At least one of 'id', 'name', or 'image' must be provided")
        return self

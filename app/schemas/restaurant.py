from pydantic import BaseModel, Field


class Restaurant(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    cuisine: str = Field(min_length=1)
    description: str = Field(min_length=1)

from pydantic import BaseModel, ConfigDict, Field


class BookSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    title: str = Field(min_length=1)
    author: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    rating: int = Field(gt=-1, lt=101)

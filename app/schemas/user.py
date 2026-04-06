from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(None, max_length=32, description="Optional; audited as ***last4")

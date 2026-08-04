from pydantic import BaseModel, EmailStr, Field


class UserOut(BaseModel):
    id: str
    name: str | None
    email: str
    role: str
    municipality_id: str | None
    department_ids: list[str]
    language: str
    digest_enabled: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class LoginOut(BaseModel):
    access_token: str
    user: UserOut


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=10)


class AcceptInviteIn(BaseModel):
    token: str
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10)
    language: str = Field(pattern="^(he|en)$")


class InviteInfoOut(BaseModel):
    email: str
    inviter_name: str | None
    municipality_name: str | None
    department_names: list[str]
    role: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10)


class TokenOut(BaseModel):
    access_token: str

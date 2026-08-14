from pydantic import BaseModel


class GenerateRequest(BaseModel):
    url: str

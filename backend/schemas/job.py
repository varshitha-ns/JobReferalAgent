from pydantic import BaseModel


class JobData(BaseModel):
    url: str
    title: str
    description: str
    hostname: str
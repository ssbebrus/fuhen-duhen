from pydantic import BaseModel

class ImageSchema(BaseModel):
    url: str
    ordering: int

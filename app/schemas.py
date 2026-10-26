"""Request and response bodies (the API contract).

Kept separate from the table models so the database layout can change
without changing what clients send and receive.
"""

from pydantic import BaseModel, Field, model_validator


class PayloadRequest(BaseModel):
    list_1: list[str] = Field(min_length=1, examples=[["first string", "second string"]])
    list_2: list[str] = Field(min_length=1, examples=[["other string", "another string"]])

    @model_validator(mode="after")
    def lists_have_same_length(self) -> "PayloadRequest":
        # Interleaving is only defined pairwise; rejecting here returns a
        # 422 before any database or transformer work happens.
        if len(self.list_1) != len(self.list_2):
            raise ValueError(
                f"list_1 and list_2 must have the same length "
                f"(got {len(self.list_1)} and {len(self.list_2)})"
            )
        return self


class PayloadCreated(BaseModel):
    id: int
    # Tells the client whether this request produced a new payload or
    # matched one generated earlier.
    created: bool
    message: str


class PayloadOut(BaseModel):
    output: str

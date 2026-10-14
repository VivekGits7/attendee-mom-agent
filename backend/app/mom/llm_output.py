from typing import Optional

from pydantic import BaseModel, Field, model_validator

class Outcome(BaseModel):
    item: str = Field(..., description="Decision or assigned action from the meeting")
    owner: Optional[str] = Field(..., description="Person responsible, if one was named")
    due_date: Optional[str] = Field(..., description="Deadline exactly as spoken, if any")


class MeetingMinutes(BaseModel):
    summary: str = Field(..., description="One or two sentences about the meeting result")
    outcomes: list[Outcome] = Field(..., description="Decisions and assigned actions")
    open_questions: list[str] = Field(..., description="Questions left unresolved")

    @model_validator(mode="before")
    @classmethod
    def read_older_minutes(cls, value):
        if not isinstance(value, dict) or "outcomes" in value:
            return value
        if "decisions" not in value and "action_items" not in value:
            return value
        outcomes = [
            {"item": decision["decision"], "owner": None, "due_date": None}
            for decision in value.get("decisions", [])
        ]
        outcomes.extend(
            {
                "item": action["task"],
                "owner": None if action.get("owner") in (None, "Unassigned") else action["owner"],
                "due_date": None if action.get("due_date") in (None, "Not specified") else action["due_date"],
            }
            for action in value.get("action_items", [])
        )
        return {
            "summary": value.get("summary", ""),
            "outcomes": outcomes,
            "open_questions": value.get("open_questions", []),
        }

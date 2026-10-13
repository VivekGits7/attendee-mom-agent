from typing import List

from pydantic import BaseModel, Field

from app.mom.enums import ActionPriority

# No field examples here because this schema goes to OpenAI strict mode, Swagger examples live on the response models.


class Decision(BaseModel):
    decision: str = Field(..., description="What was decided")
    made_by: str = Field(..., description="Speaker who confirmed it, or Group")


class ActionItem(BaseModel):
    task: str = Field(..., description="Task written as a clear action")
    owner: str = Field(..., description="Owner name from the transcript, or Unassigned")
    due_date: str = Field(..., description="Deadline as spoken, or Not specified")
    priority: ActionPriority = Field(..., description="Task urgency")


class MeetingMinutes(BaseModel):
    summary: str = Field(
        ..., description="Three to six sentence summary of the meeting"
    )
    key_points: List[str] = Field(..., description="Important topics and facts")
    decisions: List[Decision] = Field(..., description="Decisions taken in the meeting")
    action_items: List[ActionItem] = Field(
        ..., description="Tasks with owner and deadline"
    )
    open_questions: List[str] = Field(..., description="Questions left unanswered")
    attendees: List[str] = Field(..., description="Distinct speaker names")

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


def _error_example(
    status_code: int, status_message: str, message: str, code: str
) -> dict:
    return {
        "example": {
            "success": False,
            "error": {
                "status_code": status_code,
                "status_message": status_message,
                "message": message,
                "code": code,
            },
        }
    }


class BaseResponse(BaseModel):
    success: bool = Field(
        default=True, description="Whether the request succeeded", examples=[True]
    )
    message: str = Field(
        ..., description="Result message", examples=["Webhook received"]
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"success": True, "message": "Webhook received"}}
    )


class ErrorDetail(BaseModel):
    field: str = Field(
        ..., description="Path to the invalid field", examples=["body.meeting_url"]
    )
    message: str = Field(
        ..., description="What is wrong with the field", examples=["Field required"]
    )
    type: str = Field(..., description="Error type identifier", examples=["missing"])


class ErrorBody(BaseModel):
    status_code: int = Field(..., description="HTTP status code", examples=[400])
    status_message: str = Field(
        ..., description="HTTP status text", examples=["BAD REQUEST"]
    )
    message: str = Field(
        ...,
        description="User friendly error message",
        examples=["Invalid request. Please check your input."],
    )
    code: Optional[str] = Field(
        None, description="Error code for client handling", examples=["BAD_REQUEST"]
    )
    details: Optional[List[ErrorDetail]] = Field(
        None, description="Field errors on 422 responses"
    )


class _ErrorResponse(BaseModel):
    success: bool = Field(
        default=False, description="Always false for error responses", examples=[False]
    )
    error: ErrorBody = Field(..., description="Error details")


class BadRequestResponse(_ErrorResponse):
    model_config = ConfigDict(
        json_schema_extra=_error_example(
            400,
            "BAD REQUEST",
            "Invalid meeting_id format. Expected a valid UUID.",
            "BAD_REQUEST",
        )
    )


class UnauthorizedResponse(_ErrorResponse):
    model_config = ConfigDict(
        json_schema_extra=_error_example(
            401, "UNAUTHORIZED", "Invalid or missing API key", "UNAUTHORIZED"
        )
    )


class NotFoundResponse(_ErrorResponse):
    model_config = ConfigDict(
        json_schema_extra=_error_example(
            404, "NOT FOUND", "Meeting not found", "NOT_FOUND"
        )
    )


class ConflictResponse(_ErrorResponse):
    model_config = ConfigDict(
        json_schema_extra=_error_example(
            409, "CONFLICT", "The bot is not in this meeting anymore", "CONFLICT"
        )
    )


class RateLimitResponse(_ErrorResponse):
    model_config = ConfigDict(
        json_schema_extra=_error_example(
            429,
            "TOO MANY REQUESTS",
            "Rate limit exceeded. Please try again later.",
            "RATE_LIMITED",
        )
    )


class InternalServerErrorResponse(_ErrorResponse):
    model_config = ConfigDict(
        json_schema_extra=_error_example(
            500,
            "INTERNAL SERVER ERROR",
            "Something went wrong. Please try again later.",
            "INTERNAL_ERROR",
        )
    )


class BadGatewayResponse(_ErrorResponse):
    model_config = ConfigDict(
        json_schema_extra=_error_example(
            502,
            "BAD GATEWAY",
            "Service temporarily unavailable. Please try again later.",
            "EXTERNAL_SERVICE_ERROR",
        )
    )


class ValidationErrorResponse(_ErrorResponse):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": {
                    "status_code": 422,
                    "status_message": "UNPROCESSABLE ENTITY",
                    "message": "Please check your input and try again.",
                    "code": "VALIDATION_ERROR",
                    "details": [
                        {
                            "field": "body.meeting_url",
                            "message": "Field required",
                            "type": "missing",
                        }
                    ],
                },
            }
        }
    )


class HealthData(BaseModel):
    status: str = Field(..., description="Service health", examples=["healthy"])
    service: str = Field(..., description="Service name", examples=["MOM Generator"])


class HealthCheckResponse(BaseResponse):
    data: HealthData = Field(..., description="Health details")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Service is healthy",
                "data": {"status": "healthy", "service": "MOM Generator"},
            }
        }
    )


COMMON_ERROR_RESPONSES = {
    401: {
        "model": UnauthorizedResponse,
        "description": "API key, bearer token, or webhook signature missing or invalid",
    },
    422: {
        "model": ValidationErrorResponse,
        "description": "Request body failed schema validation",
    },
    429: {
        "model": RateLimitResponse,
        "description": "Rate limit exceeded for this endpoint",
    },
    500: {
        "model": InternalServerErrorResponse,
        "description": "Unexpected server error",
    },
}

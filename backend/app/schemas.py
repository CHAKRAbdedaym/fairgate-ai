from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Strict):
    claim: str = Field(min_length=1, max_length=500)
    reference: str = Field(min_length=1, max_length=2000)
    verified: bool = False


class CampaignCreate(Strict):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="Synthetic campaign", max_length=4000)
    channel: Literal["email", "sms"] = "email"
    subject: str = Field(default="", max_length=250)
    marketing_content: str = Field(min_length=1, max_length=20000)
    target_audience: str = Field(default="Synthetic audience", max_length=500)
    language: Literal["fr", "en", "ar"] = "fr"
    language_variants: dict[str, str] = Field(default_factory=dict, max_length=10)
    supporting_evidence: list[Evidence] = Field(default_factory=list, max_length=30)
    recipient_ids: list[int] = Field(default_factory=list, max_length=10000)

    @field_validator("name", "marketing_content")
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError("Must not be blank")
        return v

    @field_validator("language_variants")
    @classmethod
    def languages(cls, v):
        if any(
            k not in ["ar", "fr", "en"] or len(text) > 20000 or not text.strip()
            for k, text in v.items()
        ):
            raise ValueError(
                "Variants must use ar, fr, or en and contain 1–20,000 characters."
            )
        return v


# PATCH preserves omitted fields while retaining the create validators and limits.
from copy import deepcopy
from pydantic import create_model

_patch_fields = {}
for _name, _field in CampaignCreate.model_fields.items():
    _copy = deepcopy(_field)
    _copy.default = None
    _patch_fields[_name] = (_field.annotation, _copy)
CampaignPatch = create_model(
    "CampaignPatch",
    __base__=CampaignCreate,
    **_patch_fields,
    expected_version=(int, Field(ge=1))
)


class RemediationPatch(Strict):
    selections: dict[str, bool] = Field(max_length=10)


class Apply(Strict):
    expected_version: int = Field(ge=1)


class ApprovalRequest(Strict):
    campaign_id: int
    audit_id: int
    reviewer: str = Field(default="Local demo reviewer", min_length=1, max_length=120)
    comments: str = Field(default="", max_length=4000)


class Decision(Strict):
    reviewer: str = Field(default="Local demo reviewer", min_length=1, max_length=120)
    comments: str = Field(default="", max_length=4000)
    language_reviewed: bool = False


class Restore(Strict):
    expected_version: int = Field(ge=1)

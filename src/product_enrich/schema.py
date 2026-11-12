"""Strict enrichment JSON contract + enum validation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Gender = Literal["men", "women", "unisex", "kids", "unknown"]
GarmentType = Literal[
    "shirt",
    "t-shirt",
    "hoodie",
    "sweater",
    "blazer",
    "jacket",
    "coat",
    "dress",
    "skirt",
    "trousers",
    "jeans",
    "shorts",
    "shoes",
    "boots",
    "sneakers",
    "bag",
    "accessory",
    "hat",
    "other",
    "unknown",
]
Color = Literal[
    "black",
    "white",
    "grey",
    "beige",
    "brown",
    "navy",
    "blue",
    "green",
    "red",
    "pink",
    "purple",
    "yellow",
    "orange",
    "multicolor",
    "metallic",
    "unknown",
]
Material = Literal[
    "cotton",
    "wool",
    "denim",
    "leather",
    "synthetic",
    "linen",
    "silk",
    "unknown",
]
Style = Literal[
    "casual",
    "smart-casual",
    "formal",
    "sport",
    "streetwear",
    "minimal",
    "luxury",
    "unknown",
]
Occasion = Literal[
    "date",
    "work",
    "evening",
    "party",
    "casual",
    "outdoor",
    "travel",
    "sport",
    "unknown",
]
Season = Literal["spring", "summer", "autumn", "winter", "all-season", "unknown"]
Pattern = Literal["solid", "striped", "checked", "printed", "logo", "other", "unknown"]
Fit = Literal["slim", "regular", "relaxed", "oversized", "unknown"]

GENDER_VALUES = {"men", "women", "unisex", "kids", "unknown"}
GARMENT_TYPE_VALUES = {
    "shirt",
    "t-shirt",
    "hoodie",
    "sweater",
    "blazer",
    "jacket",
    "coat",
    "dress",
    "skirt",
    "trousers",
    "jeans",
    "shorts",
    "shoes",
    "boots",
    "sneakers",
    "bag",
    "accessory",
    "hat",
    "other",
    "unknown",
}
COLOR_VALUES = {
    "black",
    "white",
    "grey",
    "beige",
    "brown",
    "navy",
    "blue",
    "green",
    "red",
    "pink",
    "purple",
    "yellow",
    "orange",
    "multicolor",
    "metallic",
    "unknown",
}
MATERIAL_VALUES = {
    "cotton",
    "wool",
    "denim",
    "leather",
    "synthetic",
    "linen",
    "silk",
    "unknown",
}
STYLE_VALUES = {
    "casual",
    "smart-casual",
    "formal",
    "sport",
    "streetwear",
    "minimal",
    "luxury",
    "unknown",
}
OCCASION_VALUES = {
    "date",
    "work",
    "evening",
    "party",
    "casual",
    "outdoor",
    "travel",
    "sport",
    "unknown",
}
SEASON_VALUES = {"spring", "summer", "autumn", "winter", "all-season", "unknown"}
PATTERN_VALUES = {"solid", "striped", "checked", "printed", "logo", "other", "unknown"}
FIT_VALUES = {"slim", "regular", "relaxed", "oversized", "unknown"}


def _coerce_enum(value: str, allowed: set[str], default: str = "unknown") -> str:
    key = (value or "").strip().lower().replace("_", "-")
    if key in {"gray"}:
        key = "grey"
    if key in {"tshirt", "tee"}:
        key = "t-shirt"
    if key in allowed:
        return key
    return default


def _coerce_list(values: list[str], allowed: set[str], *, max_items: int) -> list[str]:
    out: list[str] = []
    for raw in values or []:
        item = _coerce_enum(str(raw), allowed)
        if item not in out:
            out.append(item)
        if len(out) >= max_items:
            break
    return out or ["unknown"]


class VisionEnrichment(BaseModel):
    """Strict JSON returned by the vision model."""

    product_id: int
    description: str = Field(min_length=1, max_length=600)
    gender: Gender
    garment_type: GarmentType
    colors: list[Color] = Field(min_length=1, max_length=3)
    material: list[Material] = Field(default_factory=lambda: ["unknown"])
    style: list[Style] = Field(min_length=1, max_length=4)
    occasion: list[Occasion] = Field(min_length=1, max_length=4)
    season: list[Season] = Field(min_length=1, max_length=2)
    pattern: Pattern
    fit: Fit
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("gender", mode="before")
    @classmethod
    def _gender(cls, v: object) -> str:
        return _coerce_enum(str(v), GENDER_VALUES)

    @field_validator("garment_type", mode="before")
    @classmethod
    def _garment(cls, v: object) -> str:
        return _coerce_enum(str(v), GARMENT_TYPE_VALUES)

    @field_validator("pattern", mode="before")
    @classmethod
    def _pattern(cls, v: object) -> str:
        return _coerce_enum(str(v), PATTERN_VALUES)

    @field_validator("fit", mode="before")
    @classmethod
    def _fit(cls, v: object) -> str:
        return _coerce_enum(str(v), FIT_VALUES)

    @field_validator("colors", mode="before")
    @classmethod
    def _colors(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            v = [v]
        return _coerce_list([str(x) for x in v], COLOR_VALUES, max_items=3)

    @field_validator("material", mode="before")
    @classmethod
    def _material(cls, v: object) -> list[str]:
        if v is None:
            return ["unknown"]
        if not isinstance(v, list):
            v = [v]
        return _coerce_list([str(x) for x in v], MATERIAL_VALUES, max_items=4)

    @field_validator("style", mode="before")
    @classmethod
    def _style(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            v = [v]
        return _coerce_list([str(x) for x in v], STYLE_VALUES, max_items=4)

    @field_validator("occasion", mode="before")
    @classmethod
    def _occasion(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            v = [v]
        return _coerce_list([str(x) for x in v], OCCASION_VALUES, max_items=4)

    @field_validator("season", mode="before")
    @classmethod
    def _season(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            v = [v]
        return _coerce_list([str(x) for x in v], SEASON_VALUES, max_items=2)

    @field_validator("description")
    @classmethod
    def _description(cls, v: str) -> str:
        text = " ".join((v or "").strip().split())
        if not text:
            raise ValueError("description is required")
        return text[:600]


def build_embedding_text(result: VisionEnrichment) -> str:
    """Build embedding input; never include price."""
    tags = (
        f"gender={result.gender}; garment_type={result.garment_type}; "
        f"colors={','.join(result.colors)}; material={','.join(result.material)}; "
        f"style={','.join(result.style)}; occasion={','.join(result.occasion)}; "
        f"season={','.join(result.season)}; pattern={result.pattern}; fit={result.fit}"
    )
    return f"{result.description}\n{tags}"

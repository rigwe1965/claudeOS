"""Client Vault schemas."""
from __future__ import annotations

import re
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
BRAND_COLOR_FIELDS = (
    "color", "accent_color", "bg_color", "hover_color", "surface_color",
    "surface2_color", "text_color", "text_muted_color", "border_color", "input_bg",
)


def is_brand_color(value: Any) -> bool:
    return isinstance(value, str) and _HEX_COLOR.fullmatch(value) is not None


def safe_brand_colors(brand: dict) -> dict:
    """Discard unsafe legacy/session colors before CSS, HTML or JS rendering."""
    return {
        key: value for key, value in brand.items()
        if key not in BRAND_COLOR_FIELDS or value in (None, "") or is_brand_color(value)
    }


def validate_brand_fields(color: Any = None, icon: Any = None, accent: Any = None,
                          *, metadata: Any = None) -> Optional[str]:
    """Return an error message if a branding value is unsafe to inject into CSS/HTML."""
    if metadata is not None and not isinstance(metadata, dict):
        return "metadata must be an object"
    colors = [("color", color), ("accent_color", accent)]
    colors.extend((key, val) for key, val in (metadata or {}).items() if key in BRAND_COLOR_FIELDS)
    for name, val in colors:
        if val not in (None, "") and not is_brand_color(val):
            return f"{name} must be a #RRGGBB hex value"
    if icon is not None and (not isinstance(icon, str) or len(icon) > 8 or any(c in icon for c in "<>&\"'`")):
        return "icon must be a short emoji or symbol"
    return None


BRAND_COLOR_META_KEYS = (
    "accent_color", "bg_color", "hover_color", "surface_color", "surface2_color",
    "text_color", "text_muted_color", "border_color", "input_bg",
)


def validate_brand_metadata(meta: Any) -> Optional[str]:
    """Return an error message if any colour in namespace metadata is not a #RRGGBB hex value."""
    if not isinstance(meta, dict):
        return None
    for key in BRAND_COLOR_META_KEYS:
        val = meta.get(key)
        if val not in (None, "") and not (isinstance(val, str) and _HEX_COLOR.match(val)):
            return f"{key} must be a #RRGGBB hex value"
    return None


class NamespaceCreate(BaseModel):
    slug: str
    display_name: str
    description: str = ""
    type: str = "client"          # client | personal | system
    color: str = "#407E3C"
    icon: str = "🏢"
    parent_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("color")
    @classmethod
    def _check_color(cls, v):
        err = validate_brand_fields(color=v)
        if err:
            raise ValueError(err)
        return v

    @field_validator("icon")
    @classmethod
    def _check_icon(cls, v):
        err = validate_brand_fields(icon=v)
        if err:
            raise ValueError(err)
        return v

    @field_validator("metadata")
    @classmethod
    def _check_metadata(cls, v):
        err = validate_brand_fields(metadata=v)
        if err:
            raise ValueError(err)
        return v


class Namespace(NamespaceCreate):
    id: str
    enabled: bool = True
    created_at: str = ""


class ProjectCreate(BaseModel):
    namespace_id: str
    name: str
    slug: str
    description: str = ""
    status: str = "active"        # active | paused | archived
    priority: int = 2             # 1=high, 2=medium, 3=low
    tech_stack: list[str] = Field(default_factory=list)
    path: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Project(ProjectCreate):
    id: str
    created_at: str = ""
    updated_at: str = ""

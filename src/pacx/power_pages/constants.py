"""Shared constants for Power Pages helpers."""

from __future__ import annotations

DEFAULT_NATURAL_KEYS: dict[str, list[str]] = {
    "adx_webpages": ["adx_partialurl", "_adx_websiteid_value"],
    "adx_webfiles": ["adx_partialurl", "_adx_websiteid_value"],
    "adx_contentsnippets": ["adx_name", "_adx_websiteid_value"],
    "adx_pagetemplates": ["adx_name", "_adx_websiteid_value"],
    "adx_sitemarkers": ["adx_name", "_adx_websiteid_value"],
    "adx_weblinksets": ["adx_name", "_adx_websiteid_value"],
    "adx_weblinks": ["adx_name", "_adx_weblinksetid_value"],
    "adx_webpageaccesscontrolrules": ["adx_name", "_adx_websiteid_value"],
    "adx_webroles": ["adx_name", "_adx_websiteid_value"],
    "adx_entitypermissions": ["adx_name", "_adx_websiteid_value"],
    "adx_redirects": ["adx_sourceurl", "_adx_websiteid_value"],
}

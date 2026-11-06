from __future__ import annotations

import logging
import uuid

from ..paths import PROJECT_ROOT

ROOT = PROJECT_ROOT

SOURCE = "https://www.erzdioezese-wien.at/site/gottesdienstsuche"

POSTCODES = "https://download.geonames.org/export/zip/AT.zip"

POPUP = "https://www.erzdioezese-wien.at/site/cust_edwnews_gottesdienste_search_popup.siteswift"

NAMESPACE = uuid.UUID("cc91fc06-05af-4f90-bd7d-5df3a8b0462f")

LOG = logging.getLogger("erzdioezese")

LANGUAGES = {
    "Deutsch": "German",
    "Englisch": "English",
    "Latein": "Latin",
    "Französisch": "French",
    "Spanisch": "Spanish",
    "Polnisch": "Polish",
    "Italienisch": "Italian",
    "Kroatisch": "Croatian",
    "Ukrainisch": "Ukrainian",
    "Rumänisch": "Romanian",
    "Ungarisch": "Hungarian",
    "Portugiesisch": "Portuguese",
    "Akan-sprachige Gemeinde": "Akan",
    "Albanisch": "Albanian",
    "Arabisch": "Arabic",
    "Armenisch": "Armenian",
    "Bengalisch": "Bengali",
    "Bulgarisch": "Bulgarian",
    "Chinesisch": "Chinese",
    "Hindi": "Hindi",
    "Igbo": "Igbo",
    "Indonesisch": "Indonesian",
    "Japanisch": "Japanese",
    "Kirchenslawisch": "Church Slavonic",
    "Koreanisch": "Korean",
    "Malayalam": "Malayalam",
    "Niederländisch": "Dutch",
    "Norwegisch": "Norwegian",
    "Russisch": "Russian",
    "Schwedisch": "Swedish",
    "Slowenisch": "Slovenian",
    "Slowakisch": "Slovak",
    "Swahili": "Swahili",
    "Tagalog": "Tagalog",
    "Tamilisch": "Tamil",
    "Tschechisch": "Czech",
    "Vietnamesisch": "Vietnamese",
}

OSM_WEBSITE_TOLERANCE_METERS = 50

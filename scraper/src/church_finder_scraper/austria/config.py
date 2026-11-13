from __future__ import annotations

import logging
import uuid

SOURCE = "https://www.gottesdienst.at/in-ihrer-naehe"
POPUP = "https://www.gottesdienst.at/site/gottesdienstsuche_search_popup.siteswift"
NAMESPACE = uuid.UUID("c20250d9-09f5-4db4-b231-ecbe05d54f0d")
LOG = logging.getLogger("gottesdienst_at")

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

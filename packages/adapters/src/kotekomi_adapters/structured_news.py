"""Deterministic, network-free structured-news provider adapters."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import cast
from xml.etree.ElementTree import Element

from bs4 import BeautifulSoup, Tag
from defusedxml import ElementTree
from kotekomi_application import (
    NewsDeliveryEnvelope,
    NewsIdentification,
    NewsProcessorIdentity,
    NewsRevisionDecision,
)
from kotekomi_domain import (
    DocumentVersionKind,
    NewsBodyElement,
    NewsBodyElementKind,
    NewsFormatPrecedence,
    NewsRevisionClassification,
    NewsRightsFacts,
    ProviderIdentity,
    ProviderNewsItem,
)

NEWSML_CONFIG_DIGEST = hashlib.sha256(b"newsml_g2_nitf_mapping_v1").hexdigest()
GENERIC_HTML_CONFIG_DIGEST = hashlib.sha256(
    b"newsarticle_jsonld_semantic_html_main_text_v1"
).hexdigest()


class NewsMLG2Adapter:
    processor_identity = NewsProcessorIdentity(
        adapter_name="newsml_g2",
        adapter_version="1",
        adapter_config_digest=NEWSML_CONFIG_DIGEST,
        output_contract_version="structured_news_representation_v1",
    )

    def identify(self, delivery: NewsDeliveryEnvelope) -> NewsIdentification:
        item = _parse_newsml(delivery.payload)
        return _identification(item)

    def parse(self, delivery: NewsDeliveryEnvelope) -> ProviderNewsItem:
        return _parse_newsml(delivery.payload)

    def classify_revision(
        self,
        identification: NewsIdentification,
        prior_revisions: tuple[NewsRevisionClassification, ...],
    ) -> NewsRevisionDecision:
        return _classify_provider_revision(identification, prior_revisions)


class GenericArticleAdapter:
    processor_identity = NewsProcessorIdentity(
        adapter_name="generic_article",
        adapter_version="1",
        adapter_config_digest=GENERIC_HTML_CONFIG_DIGEST,
        output_contract_version="structured_news_representation_v1",
    )

    def identify(self, delivery: NewsDeliveryEnvelope) -> NewsIdentification:
        return _identification(_parse_generic_article(delivery))

    def parse(self, delivery: NewsDeliveryEnvelope) -> ProviderNewsItem:
        return _parse_generic_article(delivery)

    def classify_revision(
        self,
        identification: NewsIdentification,
        prior_revisions: tuple[NewsRevisionClassification, ...],
    ) -> NewsRevisionDecision:
        if not prior_revisions:
            return NewsRevisionDecision(
                DocumentVersionKind.ORIGINAL,
                "generic_original",
                None,
                ("canonical_uri", "content_digest"),
            )
        previous = _revision_tip(prior_revisions)
        return NewsRevisionDecision(
            DocumentVersionKind.UPDATE,
            "generic_content_update",
            previous.provider_version,
            ("canonical_uri", "changed_content_digest"),
        )


def _parse_newsml(payload: bytes) -> ProviderNewsItem:
    try:
        root = ElementTree.fromstring(payload)
    except Exception as exc:
        raise ValueError("Malformed NewsML-G2 payload.") from exc
    if _local(root.tag) != "newsItem":
        raise ValueError("NewsML-G2 payload must contain one newsItem root.")
    guid = _required_attr(root, "guid")
    version = _required_attr(root, "version")
    item_meta = _required_child(root, "itemMeta")
    content_meta = _required_child(root, "contentMeta")
    version_created = _parse_datetime(_required_text(item_meta, "versionCreated"))
    first_created = _optional_datetime(_child_text(item_meta, "firstCreated"))
    provider = _child_text(_child(item_meta, "provider"), "name") or "unknown-provider"
    pub_status_element = _child(item_meta, "pubStatus")
    pub_status = (
        pub_status_element.attrib.get("qcode", "unknown")
        if pub_status_element is not None
        else "unknown"
    )
    signals = tuple(
        value
        for element in _descendants(item_meta, "signal")
        if (value := element.attrib.get("qcode"))
    )
    roles = tuple(
        text
        for element in _descendants(item_meta, "role")
        for text in _child_texts(element, "name")
    )
    provider_status = "|".join((pub_status, *signals, *roles))
    language_element = _child(content_meta, "language")
    language = language_element.attrib.get("tag") if language_element is not None else None
    headlines = tuple(_child_texts(content_meta, "headline"))
    if not headlines:
        title = _child_text(content_meta, "title")
        headlines = (title,) if title else ()
    bylines = tuple(_child_texts(content_meta, "by"))
    dateline = _child_text(content_meta, "dateline")
    subjects = tuple(
        text
        for subject in _descendants(content_meta, "subject")
        if (text := _child_text(subject, "name"))
    )
    locations = tuple(
        text
        for located in _descendants(content_meta, "located")
        if (text := _child_text(located, "name"))
    )
    rights_info = _child(root, "rightsInfo")
    usage_terms = tuple(_child_texts(rights_info, "usageTerms")) if rights_info is not None else ()
    embargo_until = _optional_datetime(_child_text(item_meta, "embargoed"))
    archive_permitted = not any(
        signal.casefold().rsplit(":", 1)[-1] == "noarchive" for signal in signals
    )
    body_elements = _newsml_body_elements(root, headlines, bylines, dateline)
    media_references = tuple(
        href
        for remote in _descendants(root, "remoteContent")
        if (href := remote.attrib.get("href"))
    )
    return ProviderNewsItem(
        identity=ProviderIdentity(
            provider_namespace=provider.casefold().replace(" ", "-"),
            provider_item_id=guid,
            provider_version=version,
            provider_status=provider_status,
            normalized_version_key=_normalized_version(version),
            canonical_uri=_canonical_link(root),
        ),
        version_created_at=version_created,
        first_published_at=first_created,
        updated_at=version_created,
        language=language,
        headlines=headlines,
        bylines=bylines,
        dateline=dateline,
        subjects=subjects,
        locations=locations,
        body_elements=body_elements,
        media_references=media_references,
        rights=NewsRightsFacts(
            usage_terms=usage_terms,
            distribution_scopes=tuple(
                str(value) for value in _safe_list(_metadata_value(root, "distribution_scopes"))
            ),
            provider_signals=(*signals, *roles),
            embargo_until=embargo_until,
            entitlement_expires_at=None,
            archive_permitted=archive_permitted,
        ),
        raw_metadata={
            "standard": root.attrib.get("standard"),
            "standardversion": root.attrib.get("standardversion"),
            "pub_status": pub_status,
        },
        format_precedence=NewsFormatPrecedence.NEWSML_G2,
    )


def _newsml_body_elements(
    root: Element,
    headlines: tuple[str, ...],
    bylines: tuple[str, ...],
    dateline: str | None,
) -> tuple[NewsBodyElement, ...]:
    raw: list[tuple[NewsBodyElementKind, str, tuple[str, ...]]] = []
    for index, headline in enumerate(headlines, start=1):
        raw.append((NewsBodyElementKind.HEADLINE, headline, ("contentMeta", f"headline[{index}]")))
    for index, byline in enumerate(bylines, start=1):
        raw.append((NewsBodyElementKind.BYLINE, byline, ("contentMeta", f"by[{index}]")))
    if dateline:
        raw.append((NewsBodyElementKind.DATELINE, dateline, ("contentMeta", "dateline[1]")))
    content_set = _child(root, "contentSet")
    inline = _child(content_set, "inlineXML") if content_set is not None else None
    if inline is not None:
        counters: dict[str, int] = {}
        for element in inline.iter():
            tag = _local(element.tag)
            kind = {
                "hl1": NewsBodyElementKind.HEADING,
                "hl2": NewsBodyElementKind.HEADING,
                "p": NewsBodyElementKind.PARAGRAPH,
                "blockquote": NewsBodyElementKind.QUOTE,
                "li": NewsBodyElementKind.LIST_ITEM,
                "caption": NewsBodyElementKind.CAPTION,
            }.get(tag)
            if kind is None:
                continue
            text = " ".join("".join(element.itertext()).split())
            if not text:
                continue
            counters[tag] = counters.get(tag, 0) + 1
            raw.append((kind, text, ("contentSet", "inlineXML", f"{tag}[{counters[tag]}]")))
    return tuple(
        NewsBodyElement(
            element_key=f"element-{index:04d}",
            kind=kind,
            order_index=index - 1,
            hierarchy_path=(kind.value, str(index)),
            source_path=path,
            text=text,
        )
        for index, (kind, text, path) in enumerate(raw, start=1)
    )


def _parse_generic_article(delivery: NewsDeliveryEnvelope) -> ProviderNewsItem:
    soup = BeautifulSoup(delivery.payload, "html.parser")
    json_ld = _newsarticle_json_ld(soup)
    canonical_uri = _canonical_html_uri(soup) or delivery.canonical_uri
    if not canonical_uri:
        raise ValueError("Generic article requires a canonical URI.")
    content_digest = hashlib.sha256(delivery.payload).hexdigest()
    headline = _json_text(json_ld, "headline") or _html_text(soup.find("h1"))
    if not headline:
        raise ValueError("Generic article requires a headline.")
    date_published = _optional_datetime(_json_text(json_ld, "datePublished"))
    date_modified = _optional_datetime(_json_text(json_ld, "dateModified"))
    fallback_time = _optional_datetime(_safe_string(delivery.safe_metadata.get("retrieved_at")))
    version_created = date_modified or date_published or fallback_time
    if version_created is None:
        raise ValueError("Generic article requires a publication, update, or retrieval timestamp.")
    body, precedence = _generic_body(soup, json_ld, headline)
    authors = _json_authors(json_ld)
    signals = tuple(
        str(value) for value in _safe_list(delivery.safe_metadata.get("rights_signals"))
    )
    usage_terms = tuple(
        str(value) for value in _safe_list(delivery.safe_metadata.get("usage_terms"))
    )
    return ProviderNewsItem(
        identity=ProviderIdentity(
            provider_namespace="generic-web",
            provider_item_id=canonical_uri,
            provider_version=content_digest,
            provider_status="published",
            normalized_version_key=content_digest,
            canonical_uri=canonical_uri,
        ),
        version_created_at=version_created,
        first_published_at=date_published,
        updated_at=date_modified,
        language=_html_language(soup),
        headlines=(headline,),
        bylines=authors,
        dateline=None,
        subjects=tuple(str(value) for value in _safe_list(json_ld.get("keywords"))),
        locations=(),
        body_elements=body,
        media_references=(),
        rights=NewsRightsFacts(
            usage_terms=usage_terms,
            distribution_scopes=tuple(
                str(value)
                for value in _safe_list(delivery.safe_metadata.get("distribution_scopes"))
            ),
            provider_signals=signals,
            embargo_until=_optional_datetime(
                _safe_string(delivery.safe_metadata.get("embargo_until"))
            ),
            entitlement_expires_at=_optional_datetime(
                _safe_string(delivery.safe_metadata.get("entitlement_expires_at"))
            ),
            archive_permitted=delivery.safe_metadata.get("archive_permitted", True) is True,
        ),
        raw_metadata={"json_ld_type": _safe_string(json_ld.get("@type"))},
        format_precedence=precedence,
    )


def _generic_body(
    soup: BeautifulSoup, json_ld: dict[str, object], headline: str
) -> tuple[tuple[NewsBodyElement, ...], NewsFormatPrecedence]:
    article_body = _json_text(json_ld, "articleBody")
    raw: list[tuple[NewsBodyElementKind, str, tuple[str, ...]]] = [
        (NewsBodyElementKind.HEADLINE, headline, ("html", "headline"))
    ]
    if article_body:
        raw.extend(
            (NewsBodyElementKind.PARAGRAPH, paragraph, ("json-ld", f"articleBody[{index}]"))
            for index, paragraph in enumerate(_paragraphs(article_body), start=1)
        )
        precedence = NewsFormatPrecedence.NEWSARTICLE_JSON_LD
    else:
        article = soup.find("article")
        root: Tag | BeautifulSoup = article if isinstance(article, Tag) else soup
        elements = tuple(root.find_all(["h2", "h3", "p", "blockquote", "li", "figcaption"]))
        precedence = (
            NewsFormatPrecedence.SEMANTIC_HTML
            if isinstance(article, Tag)
            else NewsFormatPrecedence.MAIN_TEXT_FALLBACK
        )
        for index, element in enumerate(elements, start=1):
            text = _html_text(element)
            if not text:
                continue
            kind = {
                "h2": NewsBodyElementKind.HEADING,
                "h3": NewsBodyElementKind.HEADING,
                "p": NewsBodyElementKind.PARAGRAPH,
                "blockquote": NewsBodyElementKind.QUOTE,
                "li": NewsBodyElementKind.LIST_ITEM,
                "figcaption": NewsBodyElementKind.CAPTION,
            }[element.name]
            raw.append((kind, text, ("html", element.name, str(index))))
    return (
        tuple(
            NewsBodyElement(
                element_key=f"element-{index:04d}",
                kind=kind,
                order_index=index - 1,
                hierarchy_path=(kind.value, str(index)),
                source_path=path,
                text=text,
            )
            for index, (kind, text, path) in enumerate(raw, start=1)
        ),
        precedence,
    )


def _classify_provider_revision(
    identification: NewsIdentification,
    priors: tuple[NewsRevisionClassification, ...],
) -> NewsRevisionDecision:
    if not priors:
        return NewsRevisionDecision(
            DocumentVersionKind.ORIGINAL,
            "original",
            None,
            ("provider_item_id", "provider_version", "provider_status"),
        )
    status = identification.identity.provider_status.casefold()
    kind = (
        DocumentVersionKind.WITHDRAWAL
        if any(token in status for token in ("kill", "withdraw", "canceled", "withheld"))
        else (
            DocumentVersionKind.CORRECTION
            if "correct" in status
            else (
                DocumentVersionKind.CLARIFICATION
                if "clarif" in status
                else DocumentVersionKind.UPDATE
            )
        )
    )
    previous = _revision_tip(priors)
    current_version = identification.identity.provider_version
    if (
        current_version.isdigit()
        and previous.provider_version.isdigit()
        and (int(current_version) <= int(previous.provider_version))
    ):
        raise ValueError("Provider version must advance the current revision chain.")
    return NewsRevisionDecision(
        kind,
        status,
        previous.provider_version,
        ("provider_status", "provider_version"),
    )


def _identification(item: ProviderNewsItem) -> NewsIdentification:
    return NewsIdentification(
        identity=item.identity,
        version_created_at=item.version_created_at,
        first_published_at=item.first_published_at,
        updated_at=item.updated_at,
        headlines=item.headlines,
        rights=item.rights,
        format_precedence=item.format_precedence,
    )


def _revision_tip(
    revisions: tuple[NewsRevisionClassification, ...],
) -> NewsRevisionClassification:
    predecessor_ids = {
        revision.previous_document_id
        for revision in revisions
        if revision.previous_document_id is not None
    }
    tips = tuple(revision for revision in revisions if revision.document_id not in predecessor_ids)
    if len(tips) != 1:
        raise ValueError("Provider revision history has an ambiguous current tip.")
    return tips[0]


def _newsarticle_json_ld(soup: BeautifulSoup) -> dict[str, object]:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            value = cast(object, json.loads(script.string or ""))
        except json.JSONDecodeError:
            continue
        candidates = _object_list(value)
        value_object = _object_dict(value)
        if value_object is not None:
            graph = value_object.get("@graph")
            if isinstance(graph, list):
                candidates = cast(list[object], graph)
        for candidate in candidates:
            candidate_object = _object_dict(candidate)
            if candidate_object is not None and candidate_object.get("@type") in {
                "NewsArticle",
                "Article",
            }:
                return candidate_object
    return {}


def _canonical_html_uri(soup: BeautifulSoup) -> str | None:
    link = soup.select_one('link[rel~="canonical"]')
    return _safe_string(link.get("href")) if isinstance(link, Tag) else None


def _html_language(soup: BeautifulSoup) -> str | None:
    html = soup.find("html")
    return _safe_string(html.get("lang")) if isinstance(html, Tag) else None


def _json_authors(value: dict[str, object]) -> tuple[str, ...]:
    authors = value.get("author")
    candidates = _object_list(authors)
    result: list[str] = []
    for author in candidates:
        if isinstance(author, str) and author.strip():
            result.append(author.strip())
        else:
            author_object = _object_dict(author)
            name = author_object.get("name") if author_object is not None else None
            if isinstance(name, str):
                result.append(name.strip())
    return tuple(result)


def _json_text(value: dict[str, object], key: str) -> str | None:
    return _safe_string(value.get(key))


def _paragraphs(text: str) -> tuple[str, ...]:
    values = tuple(value.strip() for value in text.split("\n") if value.strip())
    return values or (text.strip(),)


def _canonical_link(root: Element) -> str | None:
    for link in _descendants(root, "link"):
        if "canonical" in link.attrib.get("rel", "").casefold():
            return link.attrib.get("href")
    return None


def _metadata_value(root: Element, key: str) -> object:
    del root, key
    return ()


def _child(element: Element | None, name: str) -> Element | None:
    if element is None:
        return None
    return next((child for child in element if _local(child.tag) == name), None)


def _required_child(element: Element, name: str) -> Element:
    child = _child(element, name)
    if child is None:
        raise ValueError(f"NewsML-G2 payload is missing {name}.")
    return child


def _descendants(element: Element, name: str) -> tuple[Element, ...]:
    return tuple(candidate for candidate in element.iter() if _local(candidate.tag) == name)


def _child_text(element: Element | None, name: str) -> str | None:
    child = _child(element, name)
    return _xml_text(child)


def _child_texts(element: Element, name: str) -> tuple[str, ...]:
    return tuple(
        text for child in element if _local(child.tag) == name and (text := _xml_text(child))
    )


def _required_text(element: Element, name: str) -> str:
    value = _child_text(element, name)
    if value is None:
        raise ValueError(f"NewsML-G2 payload is missing {name}.")
    return value


def _required_attr(element: Element, name: str) -> str:
    value = element.attrib.get(name)
    if not value:
        raise ValueError(f"NewsML-G2 payload is missing {name}.")
    return str(value)


def _xml_text(element: Element | None) -> str | None:
    if element is None:
        return None
    text = " ".join("".join(element.itertext()).split())
    return text or None


def _html_text(element: object) -> str | None:
    if not isinstance(element, Tag):
        return None
    text = element.get_text(" ", strip=True)
    return text or None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalized_version(value: str) -> str:
    return f"{int(value):020d}" if value.isdigit() else value


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("News timestamp is not ISO-8601.") from exc


def _optional_datetime(value: str | None) -> datetime | None:
    return _parse_datetime(value) if value else None


def _safe_list(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(cast(list[object], value))
    if isinstance(value, str):
        return (value,)
    return ()


def _object_list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else [value]


def _object_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    mapping = cast(dict[object, object], value)
    return {str(key): item for key, item in mapping.items()}


def _safe_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None

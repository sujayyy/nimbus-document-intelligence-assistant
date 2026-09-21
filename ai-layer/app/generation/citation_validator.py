import re


PAGE_CITATION_PATTERN = re.compile(
    r"\[Page\s+(\d+)\]"
)


def validate_citations(
    answer: str,
    retrieved_pages: set[int],
) -> dict:

    cited_pages = {
        int(page)
        for page in PAGE_CITATION_PATTERN.findall(answer)
    }

    invalid_pages = cited_pages - retrieved_pages

    has_citations = bool(cited_pages)

    all_citations_valid = (
        has_citations and not invalid_pages
    )

    return {
        "valid": all_citations_valid,
        "cited_pages": sorted(cited_pages),
        "invalid_pages": sorted(invalid_pages),
    }
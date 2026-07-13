import pytest
from kotekomi_domain import (
    DocumentTableCell,
    DocumentTableFragment,
    TableEvidenceSelector,
)


def test_table_evidence_selector_requires_both_header_dimensions() -> None:
    with pytest.raises(ValueError, match="row and column header ancestry"):
        TableEvidenceSelector(
            table_id="tbl_fixture",
            cell_id="tcl_value",
            row_header_cell_ids=("tcl_row_header",),
            column_header_cell_ids=(),
        )


def test_table_cell_cannot_claim_itself_as_header_ancestry() -> None:
    with pytest.raises(ValueError, match="cannot be its own header"):
        DocumentTableCell(
            id="tcl_value",
            representation_id="rep_fixture",
            table_id="tbl_fixture",
            fragment_id="tfr_fixture",
            row_id="trw_fixture",
            node_id="nod_value",
            row_index=1,
            column_index=1,
            row_span=1,
            column_span=1,
            row_header_cell_ids=("tcl_value",),
            source_region_ids=("srg_value",),
        )


def test_table_fragment_cannot_continue_from_itself() -> None:
    with pytest.raises(ValueError, match="cannot continue from itself"):
        DocumentTableFragment(
            id="tfr_fixture",
            representation_id="rep_fixture",
            table_id="tbl_fixture",
            fragment_index=1,
            page_numbers=(2,),
            source_region_ids=("srg_table",),
            continued_from_fragment_id="tfr_fixture",
        )

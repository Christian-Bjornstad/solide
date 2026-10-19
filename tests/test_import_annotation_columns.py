"""Source-column faults must never silently exchange genes and references."""
import csv
import io

import pytest
from openpyxl import Workbook

from solide.importing import load_file


HEADER = ['Type', 'Genes', 'Transcript', 'Coding', 'Amino Acid Change', 'Call']
ROW = ['SNV', 'PTEN', 'NM_000314.8', 'c.19G>A', 'p.Glu7Lys', 'PRESENT']


def tsv(tmp_path, rows):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerows(rows)
    path = tmp_path / 'source.tsv'
    path.write_text(stream.getvalue(), encoding='utf8')
    return path


def test_reordered_repeated_header_updates_mapping_and_preserves_each_source_layout(tmp_path):
    reordered = ['Transcript', 'Genes', 'Type', 'Call', 'Coding', 'Amino Acid Change']
    second = ['NM_000546.6', 'TP53', 'SNV', 'PRESENT', 'c.742C>T', 'p.Arg248Trp']
    result = load_file(tsv(tmp_path, [HEADER, ROW, reordered, second]))

    assert len(result.variants) == 2
    first, last = result.variants
    assert (last.gene, last.transcript, last.kind, last.coding) == ('TP53', 'NM_000546.6', 'SNV', 'c.742C>T')
    assert first.raw['_columns'] == HEADER and first.raw['_values'] == ROW
    assert last.raw['_columns'] == reordered and last.raw['_values'] == second
    assert (first.source_row, last.source_row) == (2, 4)


def test_mislabeled_repeated_header_repairs_only_unambiguous_interpretation(tmp_path):
    reordered = ['Type', 'Transcript', 'Genes', 'Coding', 'Amino Acid Change', 'Call']
    result = load_file(tsv(tmp_path, [HEADER, ROW, reordered, ROW]))
    assert len(result.variants) == 2
    last = result.variants[1]

    assert (last.gene, last.transcript) == ('PTEN', 'NM_000314.8')
    assert last.raw['Transcript'] == 'PTEN' and last.raw['Genes'] == 'NM_000314.8'
    assert last.raw['_columns'] == reordered and last.raw['_values'] == ROW
    repair = last.raw['_annotation_column_repair']
    assert repair['source_gene'] == 'NM_000314.8' and repair['source_transcript'] == 'PTEN'
    assert repair['method'] == 'unambiguous_gene_transcript_swap'
    assert any('Rad 4:' in warning and 'byttet' in warning for warning in result.warnings)


def test_initial_swapped_columns_support_many_parallel_accessions_without_rewriting_raw(tmp_path):
    row = ['SNV', 'NM_001371656.1, NR_163974.1, NR_039676.1',
           'ARID1B,LOC115308161,MIR4466', 'c.1080delC', 'p.Gly361AlafsTer91', 'PRESENT']
    result = load_file(tsv(tmp_path, [HEADER, row]))
    variant = result.variants[0]
    assert variant.gene == row[2] and variant.transcript == row[1]
    assert variant.raw['_values'] == row and variant.raw['Genes'] == row[1]
    assert '_annotation_column_repair' in variant.raw


@pytest.mark.parametrize('gene, transcript', [
    ('NM_000314.8', ''),
    ('NM_000314.8', 'NR_163974.1'),
    ('PTEN', 'TP53'),
    ('NM_000314.8, PTEN', 'TP53, NR_163974.1'),
    ('NP_000305.3', 'PTEN'),
    ('PTCH1', '23'),
    ('PTCH1', 'NM_broken.1'),
    ('PTCH1', 'NM_000264.5;23'),
    ('PTCH1', 'NM_000264.5|not_a_reference'),
])
def test_ambiguous_or_invalid_column_types_remain_visible_but_blocked(tmp_path, gene, transcript):
    row = ['SNV', gene, transcript, 'c.19G>A', 'p.Glu7Lys', 'PRESENT']
    result = load_file(tsv(tmp_path, [HEADER, row]))
    variant = result.variants[0]
    assert (variant.gene, variant.transcript) == (gene, transcript)
    assert variant.raw.get('_annotation_issue')
    assert not variant.selected
    assert '_annotation_column_repair' not in variant.raw
    assert variant.raw['_values'] == row


@pytest.mark.parametrize('delimiter', [';', '|'])
def test_clear_inversion_supports_semicolon_and_pipe_lists(tmp_path, delimiter):
    references = delimiter.join(['NM_001371656.1', 'NR_163974.1', 'NR_039676.1'])
    genes = delimiter.join(['ARID1B', 'LOC115308161', 'MIR4466'])
    row = ['SNV', references, genes, 'c.1080delC', 'p.Gly361AlafsTer91', 'PRESENT']
    variant = load_file(tsv(tmp_path, [HEADER, row])).variants[0]
    assert (variant.gene, variant.transcript) == (genes, references)
    assert variant.raw['_values'] == row
    assert variant.raw['_annotation_column_repair']['method'] == 'unambiguous_gene_transcript_swap'
    assert not variant.raw.get('_annotation_issue')


@pytest.mark.parametrize('reference', ['', '.', '-', 'NC_000009.11', 'NG_009180.1'])
def test_optional_and_genomic_references_are_not_rejected_as_malformed_transcripts(tmp_path, reference):
    row = ['SNV', 'PTCH1', reference, '', '', 'PRESENT']
    variant = load_file(tsv(tmp_path, [HEADER, row])).variants[0]
    assert variant.transcript == reference and not variant.raw.get('_annotation_issue')


def test_changed_repeated_schema_is_rejected_instead_of_reading_old_positions(tmp_path):
    changed = HEADER[:-1] + ['Sample ID']
    with pytest.raises(ValueError, match='kolonneoppsett'):
        load_file(tsv(tmp_path, [HEADER, ROW, changed, ROW]))


def test_repeated_duplicate_header_cannot_overwrite_a_source_field(tmp_path):
    with pytest.raises(ValueError, match='Duplicate column names'):
        load_file(tsv(tmp_path, [HEADER, ROW, ['Type', 'Genes', 'Genes', 'Coding', 'Amino Acid Change', 'Call'], ROW]))


def test_competing_annotation_alias_columns_are_not_silently_prioritized(tmp_path):
    with pytest.raises(ValueError, match='samme annotasjonsfelt'):
        load_file(tsv(tmp_path, [['Type', 'Gene', 'Genes'], ['SNV', 'PTEN', 'TP53']]))


def test_header_case_is_interpreted_without_modifying_source_header_cells(tmp_path):
    header = [value.upper() for value in HEADER]
    variant = load_file(tsv(tmp_path, [header, ROW])).variants[0]
    assert (variant.gene, variant.transcript, variant.platform) == ('PTEN', 'NM_000314.8', 'Ion Reporter')
    assert variant.raw['_columns'] == header and variant.raw['_values'] == ROW


@pytest.mark.parametrize('field, value', [('Genes', 123), ('Transcript', True), ('Coding', 123), ('Amino Acid Change', 456)])
def test_excel_annotation_fields_with_nontext_cells_are_not_searchable(tmp_path, field, value):
    row = ROW.copy()
    row[HEADER.index(field)] = value
    workbook = Workbook()
    workbook.active.append(HEADER)
    workbook.active.append(row)
    path = tmp_path / 'original.xlsx'
    workbook.save(path)

    variant = load_file(path).variants[0]
    assert variant.raw.get('_annotation_issue')
    assert variant.raw['_values'] == row
    assert not variant.selected


def test_fusions_and_absent_references_are_not_mistaken_for_swapped_columns(tmp_path):
    rows = [
        ['RNA', 'A2M-/-ALK', '', '', '', 'PRESENT'],
        ['CNV', 'ERBB2', '-', '', '', 'PRESENT'],
        ['SNV', 'PTEN', 'NM_000314.8', 'c.19G>A', 'p.Glu7Lys', 'PRESENT'],
    ]
    result = load_file(tsv(tmp_path, [HEADER, *rows]))
    assert [v.gene for v in result.variants] == ['A2M-/-ALK', 'ERBB2', 'PTEN']
    assert not any(v.raw.get('_annotation_issue') or v.raw.get('_annotation_column_repair') for v in result.variants)

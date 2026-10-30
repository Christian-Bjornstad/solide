from pathlib import Path
from dataclasses import replace
from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.cosmic_syntax import gene_cdna_query,syntax_candidates,syntax_page_identity


def record():return VariantRecord(Path('source.tsv'),1,'SOURCE','BRAF','NM_004333.6:c.1799T>A',
    'p.Val600Glu',genomic_location='chr7:140453136',ref_allele='A',alt_allele='T')


def test_fallback_selects_exact_gene_and_syntax_only():
    v=record();url='https://cancer.sanger.ac.uk/cosmic/mutation/overview?id=123'
    rows=[{'gene':'BRAF','syntax':'c.1799T>A','url':url},
        {'gene':'BRAF2','syntax':'c.1799T>A','url':url+'4'},
        {'gene':'BRAF','syntax':'c.1799T>AA','url':url+'5'},
        {'gene':'BRAF','syntax':'c.1799T>A','url':'https://evil.example/cosmic/mutation/overview?id=1'}]
    assert gene_cdna_query(v)=='BRAF:c.1799T>A'
    assert syntax_candidates(rows,v)==[url]
    assert not gene_cdna_query(replace(v,symbol='BRAF,OTHER'))


def test_fallback_checks_returned_genomic_span_and_never_uses_protein_alone():
    text='Gene name BRAF AA mutation p.V600E CDS mutation c.1799T>A (Substitution) Genomic coordinates GRCh37, 7:140453136..140453136'
    assert syntax_page_identity(text,record())
    for wrong in (text.replace('BRAF','BRAF2'),text.replace('c.1799T>A','c.1799T>G'),
                  text.replace('GRCh37','GRCh38'),text.replace('140453136','140453137')):
        assert not syntax_page_identity(wrong,record())


def test_browser_query_uses_gene_cdna_when_cosmic_id_is_missing(tmp_path):
    from solide._vendor.archer.services.browser_review import BrowserReviewService
    service=BrowserReviewService(profile_root=tmp_path)
    assert service.query_url('COSMIC',record())=='https://cancer.sanger.ac.uk/cosmic/search?q=BRAF%3Ac.1799T%3EA'


def test_optional_deleted_sequence_is_an_alias_but_other_deletion_lengths_are_rejected():
    v=replace(record(),symbol='BRCA2',hgvsc='NM_000059.4:c.5217_5223del')
    url='https://cancer.sanger.ac.uk/cosmic/mutation/overview?id=123'
    assert syntax_candidates([{'gene':'BRCA2','syntax':'c.5217_5223delTTTAAGT','url':url}],v)==[url]
    assert syntax_candidates([{'gene':'BRCA2','syntax':'c.5217_5223delT','url':url}],v)==[]


def test_multiple_exact_syntax_rows_remain_ambiguous_without_visiting_a_candidate(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from solide._vendor.archer.services.browser_review import BrowserReviewService
    urls=['https://cancer.sanger.ac.uk/cosmic/mutation/overview?id=1',
          'https://cancer.sanger.ac.uk/cosmic/mutation/overview?id=2']
    rows=[{'gene':'BRAF','syntax':'c.1799T>A','url':url} for url in urls]
    visits=[]
    page=SimpleNamespace(url='https://cancer.sanger.ac.uk/cosmic/search?q=BRAF',
        goto=lambda url,**kwargs:visits.append(url),locator=lambda _:SimpleNamespace(
            evaluate_all=lambda _:rows,inner_text=lambda:'Search results'))
    service=BrowserReviewService(profile_root=tmp_path)
    monkeypatch.setattr(service,'_raise_for_cosmic_terminal_page',lambda _:None)
    result=service._lookup_cosmic_syntax(page,record(),tmp_path)
    assert result.status=='ambiguous_result' and len(visits)==1
    assert not result.raw.get('screenshots')

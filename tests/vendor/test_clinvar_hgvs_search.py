from pathlib import Path
from types import SimpleNamespace

from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.database_search import DatabaseSearchService


def test_quoted_hgvs_finds_deletion_not_indexed_in_varname_without_weakening_allele_check(monkeypatch):
    service=DatabaseSearchService();queries=[]
    record=VariantRecord(Path('synthetic.tsv'),1,'SOURCE','BRCA2','NM_000059.4:c.5217_5223del',
        genomic_location='chr13:32913708',ref_allele='ATTTAAGT',alt_allele='A')
    def request(url,params):
        if 'esearch' in url:
            queries.append(params['term'])
            ids='<Id>2</Id>' if params['term']=='"NM_000059.4:c.5217_5223del"' else '<Id>1</Id>'
            content=f'<Result><IdList>{ids}</IdList></Result>'.encode()
        else:
            alternate='A' if params['id']=='2' else 'T'
            content=(f'<Result><SequenceLocation Assembly="GRCh37" Chr="13" positionVCF="32913708" '
                f'referenceAlleleVCF="ATTTAAGT" alternateAlleleVCF="{alternate}"/></Result>').encode()
        return SimpleNamespace(content=content,raise_for_status=lambda:None)
    monkeypatch.setattr(service,'_eutils_get',request)
    result=service._search_clinvar(record)
    assert result.status=='found'
    assert result.raw['clinvar_id']=='2'
    assert result.raw['matched_location']['reference']=='ATTTAAGT'
    assert '"NM_000059.4:c.5217_5223del"' in queries
